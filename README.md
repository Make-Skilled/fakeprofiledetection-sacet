# Instagram Clone

A Flask-based Instagram clone with user authentication, image uploads, likes, and comments functionality.

## Features

- User registration and login
- Image upload and posting
- Like and comment on posts
- Responsive design with Tailwind CSS
- SQLite database for data storage

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd instagram-clone
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Make sure you're in the project directory and your virtual environment is activated.

2. Run the Flask application:
```bash
python app.py
```

3. Open your web browser and navigate to:
```
http://localhost:5000
```

## Project Structure

```
instagram-clone/
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── static/            # Static files (images, CSS, etc.)
│   └── uploads/       # User uploaded images
├── templates/         # HTML templates
│   ├── base.html      # Base template
│   ├── index.html     # Home page
│   ├── login.html     # Login page
│   ├── register.html  # Registration page
│   └── create_post.html # Create new post page
└── instance/         # Instance-specific files
    └── instagram.db  # SQLite database
```

## Usage

1. Register a new account
2. Log in with your credentials
3. Create new posts by uploading images and adding captions
4. Like and comment on other users' posts
5. View your feed on the home page

## Security Notes

- The application uses SQLite for simplicity, but for production use, consider using a more robust database like PostgreSQL
- Passwords are hashed using Werkzeug's security functions
- File uploads are restricted to image files only
- The secret key should be changed in production

## Contributing

Feel free to submit issues and enhancement requests! 