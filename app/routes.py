from collections import defaultdict
from flask import (
    json,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Blueprint,
    abort,
)
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Article, VerificationAssignment
from app import db

bp = Blueprint("main", __name__)


@bp.route("/")
@bp.route("/login", methods=["GET", "POST"])
def login():
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
    """Redirects user to their first unreviewed article, or shows an empty dashboard with stats."""
    first_article_id = None

    if current_user.role == "admin":
        first_article = Article.query.order_by(Article.id).first()
        if first_article:
            first_article_id = first_article.id
    else:  # Verificator
        first_unreviewed = (
            current_user.assignments.filter_by(is_reviewed=False)
            .order_by(VerificationAssignment.article_id)
            .first()
        )
        if first_unreviewed:
            first_article_id = first_unreviewed.article_id
        else:  # All articles are reviewed, go to the first one in their list
            first_assigned = current_user.assignments.order_by(
                VerificationAssignment.article_id
            ).first()
            if first_assigned:
                first_article_id = first_assigned.article_id

    if first_article_id:
        return redirect(url_for("main.dashboard", article_id=first_article_id))
    else:
        # Handle case where there are no articles to show
        reviewed_count = 0
        total_count = 0
        if current_user.role == "admin":
            total_count = VerificationAssignment.query.count()
            reviewed_count = VerificationAssignment.query.filter_by(
                is_reviewed=True
            ).count()
        else:  # Verificator
            total_count = current_user.assignments.count()
            reviewed_count = current_user.assignments.filter_by(
                is_reviewed=True
            ).count()

        if total_count > 0 and reviewed_count == total_count:
            flash(
                "Congratulations! You have reviewed all your assigned articles.",
                "success",
            )
        else:
            flash(
                "No articles assigned to you or no articles in the database.", "warning"
            )

        return render_template(
            "dashboard.html",
            article=None,
            reviewed_count=reviewed_count,
            total_count=total_count,
        )


@bp.route("/dashboard/<int:article_id>")
@login_required
def dashboard(article_id):
    """Displays an article and calculates progress stats."""
    assignment = None
    if current_user.role == "verificator":
        assignment = current_user.assignments.filter_by(article_id=article_id).first()
        if not assignment:
            abort(403)

    article = Article.query.options(db.joinedload(Article.llm_results)).get_or_404(
        article_id
    )

    # --- Counter Logic ---
    reviewed_count = 0
    total_count = 0
    if current_user.role == "admin":
        # Admin sees overall progress of all assignments in the system
        total_count = VerificationAssignment.query.count()
        reviewed_count = VerificationAssignment.query.filter_by(
            is_reviewed=True
        ).count()
    else:  # Verificator
        # Verificator sees their personal progress
        total_count = current_user.assignments.count()
        reviewed_count = current_user.assignments.filter_by(is_reviewed=True).count()

    # --- Navigation Logic ---
    assigned_ids = []
    if current_user.role == "admin":
        assigned_ids = [a.id for a in Article.query.order_by(Article.id).all()]
    else:
        assignments = current_user.assignments.order_by(
            VerificationAssignment.article_id
        ).all()
        assigned_ids = [a.article_id for a in assignments]

    try:
        current_index = assigned_ids.index(article_id)
        prev_id = assigned_ids[current_index - 1] if current_index > 0 else None
        next_id = (
            assigned_ids[current_index + 1]
            if current_index < len(assigned_ids) - 1
            else None
        )
    except ValueError:
        current_index, prev_id, next_id = -1, None, None

    return render_template(
        "dashboard.html",
        article=article,
        assignment=assignment,
        prev_id=prev_id,
        next_id=next_id,
        reviewed_count=reviewed_count,
        total_count=total_count,
    )


@bp.route("/verify/<int:article_id>", methods=["POST"])
@login_required
def submit_verification(article_id):
    if current_user.role != "verificator":
        flash("Only verificators can submit reviews.", "danger")
        return redirect(url_for("main.dashboard", article_id=article_id))
    assignment = current_user.assignments.filter_by(
        article_id=article_id
    ).first_or_404()
    decision = request.form.get("is_relevant")
    if decision is None:
        flash(
            "You must select a verification status (Relevant or Not Relevant).",
            "warning",
        )
        return redirect(url_for("main.dashboard", article_id=article_id))
    assignment.is_relevant = decision == "true"
    assignment.is_reviewed = True
    db.session.commit()
    flash(f"Verification for article #{article_id} saved successfully.", "success")
    assignments = current_user.assignments.order_by(
        VerificationAssignment.article_id
    ).all()
    assigned_ids = [a.article_id for a in assignments]
    try:
        current_index = assigned_ids.index(article_id)
        if current_index < len(assigned_ids) - 1:
            next_id = assigned_ids[current_index + 1]
            return redirect(url_for("main.dashboard", article_id=next_id))
    except ValueError:
        pass
    return redirect(url_for("main.dashboard_redirect"))


@bp.route("/analysis")
@login_required
def analysis():
    """Renders the analysis page with chart data."""
    if current_user.role != "admin":
        abort(403)

    # --- Data Aggregation ---
    # { relevant_count: { source: article_count } }
    analysis_data = defaultdict(lambda: defaultdict(int))
    all_sources = set()
    total_articles = 0

    articles = Article.query.options(db.joinedload(Article.llm_results)).all()
    if not articles:
        return render_template("analysis.html", chart_data=json.dumps({}))

    total_articles = len(articles)
    for article in articles:
        relevant_count = sum(1 for result in article.llm_results if result.is_relevant)
        source = article.source or "Unknown"
        analysis_data[relevant_count][source] += 1
        all_sources.add(source)

    # --- Prepare Data for Chart.js ---
    sorted_sources = sorted(list(all_sources))
    labels = sorted(analysis_data.keys())

    datasets = []
    # Define some colors for the chart
    colors = [
        "rgba(67, 56, 202, 0.7)",
        "rgba(219, 39, 119, 0.7)",
        "rgba(245, 158, 11, 0.7)",
        "rgba(16, 185, 129, 0.7)",
        "rgba(99, 102, 241, 0.7)",
    ]

    for i, source in enumerate(sorted_sources):
        data_points = []
        raw_data_points = []
        for label in labels:
            count = analysis_data[label].get(source, 0)
            # Calculate percentage
            percentage = (count / total_articles) * 100 if total_articles > 0 else 0
            data_points.append(percentage)
            raw_data_points.append(count)

        datasets.append(
            {
                "label": source,
                "data": data_points,
                "raw_data": raw_data_points,  # Custom property for tooltip
                "backgroundColor": colors[i % len(colors)],
            }
        )

    chart_data = {"labels": [str(label) for label in labels], "datasets": datasets}

    return render_template("analysis.html", chart_data=json.dumps(chart_data))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for("main.login"))
