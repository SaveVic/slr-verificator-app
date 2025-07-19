from app import create_app

# Create an instance of the Flask application using the factory function
app = create_app()

if __name__ == "__main__":
    # Run the app in debug mode
    # In a production environment, you would use a proper WSGI server like Gunicorn or uWSGI
    app.run(debug=True)
