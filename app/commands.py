from collections import defaultdict
import random
import click
import pandas as pd
import pickle
import zipfile
import os
import re
from app import db
from app.models import User, Article, LLMResult, VerificationAssignment
from sqlalchemy.exc import IntegrityError


def register_commands(app):
    """Register all custom CLI commands with the Flask app."""

    @app.cli.command("init-db")
    def init_db():
        """Creates all database tables from the models. Run this first."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-users")
    def seed_users():
        """Seeds the database with predefined users."""
        with app.app_context():
            click.echo("Seeding users...")
            users_to_seed = [
                {"username": "waff", "password": "waff", "role": "verificator"},
                {"username": "hady", "password": "hady", "role": "verificator"},
                {"username": "amal", "password": "amal", "role": "verificator"},
                {"username": "wicak", "password": "wicak", "role": "verificator"},
                {"username": "elva", "password": "elva", "role": "verificator"},
                {"username": "fadil", "password": "fadil", "role": "verificator"},
                {"username": "humay", "password": "humay", "role": "verificator"},
                {"username": "admin", "password": "admin", "role": "admin"},
            ]
            for user_data in users_to_seed:
                user = User.query.filter_by(username=user_data["username"]).first()
                if not user:
                    new_user = User(username=user_data["username"])
                    new_user.set_password(user_data["password"])
                    db.session.add(new_user)
                    click.echo(
                        f"  - User '{user_data['username']}' ({user_data['role']}) created."
                    )
                else:
                    # Optionally update the role of existing users
                    user.role = user_data["role"]
                    click.echo(
                        f"  - User '{user_data['username']}' already exists. Role set to '{user_data['role']}'."
                    )
            db.session.commit()
            click.echo("User seeding complete.")

    @app.cli.command("seed-articles")
    @click.argument("csv_filepath", type=click.Path(exists=True))
    def seed_articles(csv_filepath):
        """Seeds the database with articles from a CSV file."""
        with app.app_context():
            click.echo(f"Seeding articles from '{csv_filepath}'...")
            try:
                df = pd.read_csv(csv_filepath)
                if "source" not in df.columns:
                    df["source"] = None

                for index, row in df.iterrows():
                    # Check if article with this DOI already exists
                    exists = Article.query.filter_by(doi=row["DOI"]).first()
                    if not exists:
                        article = Article(
                            doi=row["DOI"],
                            title=row["Title"],
                            abstract=row["Abstract"],
                            year=int(row["Year"]) if pd.notna(row["Year"]) else None,
                            source=row["source"] if pd.notna(row["source"]) else None,
                        )
                        db.session.add(article)
                        click.echo(f"  - Added article: {row['DOI']}")
                    else:
                        click.echo(
                            f"  - Article with DOI {row['DOI']} already exists. Skipping."
                        )

                db.session.commit()
                click.echo("Article seeding complete.")
            except Exception as e:
                click.echo(f"An error occurred during article seeding: {e}", err=True)
                db.session.rollback()

    @app.cli.command("seed-llm")
    @click.argument("zip_filepaths", nargs=-1, type=click.Path(exists=True))
    @click.option(
        "--model-name", default="Unknown-LLM", help="Name of the LLM model used."
    )
    @click.option("--cost-in", type=float, default=1, help="LLM input cost / 1M tokens")
    @click.option(
        "--cost-out", type=float, default=1, help="LLM output cost / 1M tokens"
    )
    def seed_llm(zip_filepaths, model_name, cost_in, cost_out):
        """Seeds the database with LLM results from one or more zip files."""
        if not zip_filepaths:
            click.echo(
                "No zip files provided. Please specify the path to at least one zip file.",
                err=True,
            )
            return

        with app.app_context():
            for zip_filepath in zip_filepaths:
                click.echo(
                    f"\nProcessing LLM results for model '{model_name}' from '{zip_filepath}'..."
                )

                try:
                    with zipfile.ZipFile(zip_filepath, "r") as z:
                        for filename in z.namelist():
                            if filename.startswith("__MACOSX/") or filename.endswith(
                                "/"
                            ):
                                continue

                            match = re.search(r"res-(\d+)\.pkl$", filename)
                            if not match:
                                continue

                            article_id = int(match.group(1))
                            if not Article.query.get(article_id):
                                click.echo(
                                    f"  - Warning: No article found for ID {article_id}. Skipping.",
                                    err=True,
                                )
                                continue

                            # Check if this specific result already exists
                            exists = LLMResult.query.filter_by(
                                article_id=article_id, llm_model_name=model_name
                            ).first()
                            if exists:
                                click.echo(
                                    f"  - Result for article ID {article_id} and model '{model_name}' already exists. Skipping."
                                )
                                continue

                            with z.open(filename) as pkl_file:
                                data = pickle.load(pkl_file)

                            result_data = data.get("result", {})
                            usage_data = data.get("usage", {})

                            llm_result = LLMResult(
                                success=data.get("success", False),
                                raw=data.get("raw"),
                                is_relevant=result_data.get("is_relevant"),
                                justification=result_data.get("justification"),
                                duration=usage_data.get("duration"),
                                num_token_in=usage_data.get("num_token_in", 0)
                                * cost_in,
                                num_token_out=usage_data.get("num_token_out", 0)
                                * cost_out,
                                llm_model_name=model_name,
                                article_id=article_id,
                            )
                            llm_result.addressed_areas = result_data.get(
                                "addressed_areas"
                            )

                            db.session.add(llm_result)
                            click.echo(
                                f"  - Adding result for article ID {article_id}."
                            )

                    db.session.commit()
                    click.echo(f"Finished processing '{zip_filepath}'.")
                except Exception as e:
                    click.echo(
                        f"An error occurred processing {zip_filepath}: {e}", err=True
                    )
                    db.session.rollback()

        click.echo("\nLLM result seeding process complete!")

    @app.cli.command("seed-assignments")
    def seed_assignments():
        """Assigns each article to two different verificators randomly and evenly."""
        with app.app_context():
            click.echo("Creating verification assignments...")

            # Clear existing assignments to ensure a fresh start
            VerificationAssignment.query.delete()
            db.session.commit()
            click.echo("  - Cleared all previous assignments.")

            articles = Article.query.all()
            verificators = User.query.filter_by(role="verificator").all()

            if not articles:
                click.echo(
                    "Error: No articles found in the database. Please run 'seed-articles' first.",
                    err=True,
                )
                return
            if len(verificators) < 2:
                click.echo(
                    "Error: At least two users with the 'verificator' role are required.",
                    err=True,
                )
                return

            article_ids = [a.id for a in articles]
            verificator_ids = [v.id for v in verificators]

            # Create a list of all review slots that need to be filled (2 for each article)
            review_slots = article_ids * 2
            random.shuffle(review_slots)

            # Dictionary to track assignments and prevent duplicates
            assignments = defaultdict(list)
            # Dictionary to track the load of each verificator
            load = defaultdict(int)

            for article_id in review_slots:
                # Sort verificators by their current load, then randomly to break ties
                sorted_verificators = sorted(
                    verificator_ids, key=lambda v_id: (load[v_id], random.random())
                )

                assigned_verificator = None
                for v_id in sorted_verificators:
                    # Find a verificator who is not already assigned to this article
                    if v_id not in assignments[article_id]:
                        assigned_verificator = v_id
                        break

                if assigned_verificator:
                    assignments[article_id].append(assigned_verificator)
                    load[assigned_verificator] += 1
                else:
                    # This case should ideally not be hit with this logic, but is a safeguard
                    click.echo(
                        f"Warning: Could not find a suitable second verificator for article {article_id}",
                        err=True,
                    )

            # Create the assignment objects in the database
            new_assignments_count = 0
            for article_id, assigned_ids in assignments.items():
                for user_id in assigned_ids:
                    assignment = VerificationAssignment(
                        article_id=article_id, user_id=user_id
                    )
                    db.session.add(assignment)
                    new_assignments_count += 1

            db.session.commit()
            click.echo(
                f"  - Successfully created {new_assignments_count} new assignments."
            )
            click.echo("Assignment distribution:")
            for v_id, count in sorted(load.items()):
                user = User.query.get(v_id)
                click.echo(f"  - {user.username}: {count} articles")
