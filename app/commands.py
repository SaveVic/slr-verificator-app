import click
import pandas as pd
from app import db
from app.models import User, Article


def register_commands(app):
    """Register CLI commands with the Flask app."""

    @app.cli.command("seed-db")
    def seed_db():
        """Seeds the database with users and articles."""
        with app.app_context():
            db.drop_all()
            db.create_all()

            # --- Seed Users ---
            click.echo("Seeding users...")
            users_to_seed = [
                {"username": "waffiq", "password": "waffiq"},
                {"username": "elva", "password": "elva"},
                {"username": "hady", "password": "hady"},
                {"username": "amal", "password": "amal"},
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
                # The path is now relative to the project root
                csv_path = "data/research_articles.csv"
                df = pd.read_csv(csv_path)

                for index, row in df.iterrows():
                    article = Article(
                        doi=row["DOI"],
                        title=row["Title"],
                        abstract=row["Abstract"],
                        year=int(row["Year"]) if pd.notna(row["Year"]) else None,
                    )
                    db.session.add(article)

                db.session.commit()
                click.echo(f"{len(df)} articles processed and seeded.")

            except FileNotFoundError:
                click.echo(
                    f"Error: '{csv_path}' not found. Make sure it's in the /data directory."
                )
            except Exception as e:
                click.echo(f"An error occurred during article seeding: {e}")
                db.session.rollback()

        click.echo("Database seeding complete!")
