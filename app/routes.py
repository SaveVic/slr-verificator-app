from flask import abort, render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Article, VerificationAssignment
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
    """Redirects user to the first article in their assigned queue."""
    first_article_id = None

    if current_user.role == "admin":
        # Admin sees the first article in the entire database
        first_article = Article.query.order_by(Article.id).first()
        if first_article:
            first_article_id = first_article.id
    else:
        # Verificator sees the first article in their assignment list
        first_assignment = current_user.assignments.order_by(
            VerificationAssignment.article_id
        ).first()
        if first_assignment:
            first_article_id = first_assignment.article_id

    if first_article_id:
        return redirect(url_for("main.dashboard", article_id=first_article_id))
    else:
        # If no articles are found for the user, show the empty dashboard
        flash("No articles assigned to you or no articles in the database.", "warning")
        return render_template("dashboard.html", article=None)


@bp.route("/dashboard/<int:article_id>")
@login_required
def dashboard(article_id):
    """
    Displays a single article.
    - Admins can see any article.
    - Verificators can only see articles assigned to them.
    - Prev/Next buttons navigate through the user's specific queue.
    """
    # Authorization Check
    if current_user.role == "verificator":
        # Check if the user is assigned to this article
        assignment = current_user.assignments.filter_by(article_id=article_id).first()
        if not assignment:
            # If not assigned, deny access
            abort(403)

    article = Article.query.options(db.joinedload(Article.llm_results)).get_or_404(
        article_id
    )

    # Navigation Logic
    assigned_ids = []
    if current_user.role == "admin":
        # Admin's queue is all articles
        assigned_ids = [a.id for a in Article.query.order_by(Article.id).all()]
    else:
        # Verificator's queue is their assigned articles
        assignments = current_user.assignments.order_by(
            VerificationAssignment.article_id
        ).all()
        assigned_ids = [a.article_id for a in assignments]

    # Find current index and get prev/next IDs
    try:
        current_index = assigned_ids.index(article_id)
        prev_id = assigned_ids[current_index - 1] if current_index > 0 else None
        next_id = (
            assigned_ids[current_index + 1]
            if current_index < len(assigned_ids) - 1
            else None
        )
    except ValueError:
        # This case should not happen if authorization passes, but as a safeguard:
        current_index, prev_id, next_id = -1, None, None

    return render_template(
        "dashboard.html", article=article, prev_id=prev_id, next_id=next_id
    )


@bp.route("/logout")
@login_required
def logout():
    """Logs the user out."""
    logout_user()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for("main.login"))
