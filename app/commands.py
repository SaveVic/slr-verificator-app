import click
import pandas as pd
import pickle
import zipfile
import os
import re
from app import db
from app.models import User, Article, LLMResult


def register_commands(app):
    """Register CLI commands with the Flask app."""

    @app.cli.command("seed-db")
    @click.argument("zip_filepath", type=click.Path(exists=True))
    @click.option(
        "--model-name", default="GPT-4-Analysis", help="Name of the LLM model used."
    )
    def seed_db(zip_filepath, model_name):
        """
        Seeds the database with users, articles, and LLM results from a zip file.

        ZIP_FILEPATH: Path to the zip file containing .pkl results.
        """
        with app.app_context():
            click.echo("Dropping all tables and recreating...")
            db.drop_all()
            db.create_all()

            # --- Seed Users ---
            click.echo("Seeding users...")
            users_to_seed = [
                {"username": "viewer1", "password": "password123"},
                {"username": "viewer2", "password": "password456"},
                {"username": "admin", "password": "adminpassword"},
            ]
            for user_data in users_to_seed:
                new_user = User(username=user_data["username"])
                new_user.set_password(user_data["password"])
                db.session.add(new_user)
            db.session.commit()
            click.echo("Users seeded.")

            # --- Seed Articles ---
            click.echo("Seeding articles from CSV...")
            try:
                csv_path = "data/research_articles.csv"
                df = pd.read_csv(csv_path)
                # Ensure the 'source' column exists, fill missing with None
                if "source" not in df.columns:
                    df["source"] = None
                for index, row in df.iterrows():
                    article = Article(
                        doi=row["DOI"],
                        title=row["Title"],
                        abstract=row["Abstract"],
                        year=int(row["Year"]) if pd.notna(row["Year"]) else None,
                        source=row["source"] if pd.notna(row["source"]) else None,
                    )
                    db.session.add(article)
                db.session.commit()
                click.echo(f"{len(df)} articles processed and seeded.")
            except FileNotFoundError:
                click.echo(
                    f"Error: '{csv_path}' not found. Make sure it's in the /data directory."
                )
                return
            except Exception as e:
                click.echo(f"An error occurred during article seeding: {e}")
                db.session.rollback()
                return

            # --- Seed LLM Results from Zip File ---
            click.echo(f"Processing LLM results from '{zip_filepath}'...")
            try:
                with zipfile.ZipFile(zip_filepath, "r") as z:
                    for filename in z.namelist():
                        # Ignore macOS metadata files and folders
                        if filename.startswith("__MACOSX/") or filename.endswith("/"):
                            continue

                        # Extract article ID from filename "res-{id}.pkl"
                        match = re.search(r"res-(\d+)\.pkl$", filename)
                        if not match:
                            click.echo(f"  - Skipping non-matching file: {filename}")
                            continue

                        article_id = int(match.group(1))

                        # Check if the corresponding article exists
                        article = Article.query.get(article_id)
                        if not article:
                            click.echo(
                                f"  - Warning: No article found for ID {article_id}. Skipping."
                            )
                            continue

                        # Load the pickle data
                        with z.open(filename) as pkl_file:
                            data = pickle.load(pkl_file)

                        # Create the LLMResult object
                        result_data = data.get("result", {})
                        usage_data = data.get("usage", {})

                        llm_result = LLMResult(
                            success=data.get("success", False),
                            raw=data.get("raw"),
                            is_relevant=result_data.get("is_relevant"),
                            justification=result_data.get("justification"),
                            duration=usage_data.get("duration"),
                            num_token_in=usage_data.get("num_token_in"),
                            num_token_out=usage_data.get("num_token_out"),
                            llm_model_name=model_name,
                            article_id=article_id,
                        )
                        # Use the setter for addressed_areas
                        llm_result.addressed_areas = result_data.get("addressed_areas")

                        db.session.add(llm_result)
                        click.echo(f"  - Loaded result for article ID {article_id}.")

                db.session.commit()
                click.echo("LLM results seeded successfully.")

            except zipfile.BadZipFile:
                click.echo(
                    f"Error: The file at '{zip_filepath}' is not a valid zip file."
                )
            except Exception as e:
                click.echo(f"An error occurred during LLM result seeding: {e}")
                db.session.rollback()

        click.echo("Database seeding complete!")
