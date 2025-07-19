from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Article
from app import db

# Create a Blueprint. This is a way to organize routes.
bp = Blueprint("main", __name__)


@bp.route("/")
@bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles the login page and user authentication."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard_redirect"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("main.dashboard_redirect"))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template("login.html")


@bp.route("/dashboard")
@login_required
def dashboard_redirect():
    """Redirects to the first article in the dashboard."""
    first_article = Article.query.order_by(Article.id).first()
    if first_article:
        return redirect(url_for("main.dashboard", article_id=first_article.id))
    else:
        flash("No articles found in the database.", "warning")
        return render_template("dashboard.html", article=None)


@bp.route("/dashboard/<int:article_id>")
@login_required
def dashboard(article_id):
    """Displays a single article and navigation."""
    article = Article.query.get_or_404(article_id)

    prev_article = (
        Article.query.filter(Article.id < article_id)
        .order_by(Article.id.desc())
        .first()
    )
    next_article = (
        Article.query.filter(Article.id > article_id).order_by(Article.id.asc()).first()
    )

    return render_template(
        "dashboard.html",
        article=article,
        prev_id=prev_article.id if prev_article else None,
        next_id=next_article.id if next_article else None,
    )


@bp.route("/logout")
@login_required
def logout():
    """Logs the user out."""
    logout_user()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for("main.login"))
