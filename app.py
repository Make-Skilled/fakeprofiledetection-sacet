from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import shutil
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instagram.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Copy default profile picture if it doesn't exist
default_pic_path = os.path.join(app.config['UPLOAD_FOLDER'], 'default.jpg')
if not os.path.exists(default_pic_path):
    shutil.copy('static/default.jpg', default_pic_path)

# Serve files from upload folder
@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    profile_pic = db.Column(db.String(120), default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    is_fake = db.Column(db.Boolean, default=False)  # Field for fake account detection
    risk_score = db.Column(db.Float, default=0.0)   # Risk score from 0 to 1
    warning_count = db.Column(db.Integer, default=0)  # Number of warnings received
    last_warning_date = db.Column(db.DateTime)  # Date of last warning
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def calculate_risk_score(self):
        """Calculate risk score based on various factors"""
        score = 0.0
        
        # Factor 1: Account age (newer accounts are riskier)
        account_age = (datetime.utcnow() - self.created_at).days
        if account_age < 7:
            score += 0.3
        elif account_age < 30:
            score += 0.2
        
        # Factor 2: Post frequency
        if len(self.posts) > 0:
            posts_per_day = len(self.posts) / max(account_age, 1)
            if posts_per_day > 5:  # Unusually high posting frequency
                score += 0.2
        
        # Factor 3: Comment sentiment (simplified)
        toxic_words = ['hate', 'kill', 'die', 'stupid', 'fake', 'scam', 'ugly']
        toxic_comment_count = 0
        for comment in self.comments:
            if any(word in comment.content.lower() for word in toxic_words):
                toxic_comment_count += 1
        if toxic_comment_count > 0:
            score += min(0.3, toxic_comment_count * 0.1)
        
        # Factor 4: Like-to-Post ratio
        if len(self.posts) > 0:
            like_ratio = len(self.likes) / len(self.posts)
            if like_ratio > 10:  # Unusually high like activity
                score += 0.2
        
        self.risk_score = min(1.0, score)
        return self.risk_score

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(120), nullable=False)
    caption = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_ai_generated = db.Column(db.Boolean, default=False)  # New field for AI detection
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    users = User.query.all() if current_user.is_authenticated else []
    return render_template('index.html', posts=posts, users=users)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Set as admin if it's the admin credentials
        if username == 'admin' and password == '1234':
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard' if user.is_admin else 'index'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/post/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        image = request.files.get('image')
        caption = request.form.get('caption')
        
        if image:
            filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{image.filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            post = Post(image_path=filename, caption=caption, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            
            return redirect(url_for('index'))
    
    return render_template('create_post.html')

@app.route('/post/<int:post_id>/like')
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
    
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    
    if content:
        comment = Comment(content=content, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('admin_dashboard.html', users=users, posts=posts)

@app.route('/admin/delete_post/<int:post_id>')
@login_required
def admin_delete_post(post_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    post = Post.query.get_or_404(post_id)
    
    # Delete the image file
    if post.image_path:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/warn_user/<int:user_id>')
@login_required
def warn_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot warn admin account', 'error')
        return redirect(url_for('admin_dashboard'))
    
    user.warning_count += 1
    user.last_warning_date = datetime.utcnow()
    
    warning_message = f"Warning {user.warning_count}/3: Your account has been flagged for suspicious activity. "
    if user.warning_count >= 3:
        warning_message += "This is your final warning. Further violations will result in account deletion."
    else:
        remaining = 3 - user.warning_count
        warning_message += f"You have {remaining} {'warning' if remaining == 1 else 'warnings'} remaining."
    
    flash(warning_message, 'warning')
    db.session.commit()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if user_id == current_user.id:
        flash('Cannot delete admin account', 'error')
        return redirect(url_for('admin_dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.warning_count < 3 and not user.is_fake:
        flash('User must receive 3 warnings before deletion, unless marked as fake.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Delete all user's posts and their images
    for post in user.posts:
        if post.image_path:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        # Delete all comments on this post
        Comment.query.filter_by(post_id=post.id).delete()
        # Delete all likes on this post
        Like.query.filter_by(post_id=post.id).delete()
    
    # Delete all comments made by the user
    Comment.query.filter_by(user_id=user.id).delete()
    # Delete all likes made by the user
    Like.query.filter_by(user_id=user.id).delete()
    # Delete all posts
    Post.query.filter_by(user_id=user.id).delete()
    # Finally delete the user
    db.session.delete(user)
    db.session.commit()
    
    flash('Account deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/profile/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        profile_pic = request.files.get('profile_pic')
        
        if profile_pic:
            # Generate unique filename with timestamp
            filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{profile_pic.filename}"
            profile_pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # Delete old profile picture if it's not the default
            if current_user.profile_pic != 'default.jpg':
                old_pic_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_pic)
                if os.path.exists(old_pic_path):
                    os.remove(old_pic_path)
            
            current_user.profile_pic = filename
            db.session.commit()
            flash('Profile picture updated successfully!', 'success')
        
        return redirect(url_for('user_profile', username=current_user.username))
    
    return render_template('edit_profile.html')

@app.route('/admin/analyze_account/<int:user_id>')
@login_required
def analyze_account(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    risk_score = user.calculate_risk_score()
    db.session.commit()
    
    return jsonify({
        'risk_score': risk_score,
        'account_type': 'suspicious' if user.is_fake else 'normal'
    })

@app.route('/admin/mark_account/<int:user_id>/<status>')
@login_required
def mark_account(user_id, status):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_fake = (status == 'fake')
    db.session.commit()
    
    flash(f'Account marked as {status}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/search_accounts')
@login_required
def search_accounts():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    query = request.args.get('query', '')
    account_type = request.args.get('type', '')
    
    users = User.query
    
    if query:
        users = users.filter(User.username.ilike(f'%{query}%'))
    
    if account_type:
        users = users.filter(User.is_fake == (account_type == 'fake'))
    
    users = users.all()
    return render_template('admin_search.html', users=users, query=query, account_type=account_type)

# Function to create dummy data
def create_dummy_data():
    # Real accounts with professional/normal content
    real_accounts = [
        {
            "username": "travel_photographer",
            "email": "travel.photo@example.com",
            "bio": "Professional photographer 📸 | Travel enthusiast 🌎 | Capturing world's beauty",
            "profile_pic": "360_F_286098390_D2J4jLbOkCzikuSXxQBh26IxhR7t4i28.webp",
            "posts": [
                {
                    "caption": "Ancient wonders of Athens. The architecture here is breathtaking! 🏛️ #travel #photography #athens",
                    "image": "A1381-Cities-on-every-Architectural-Photographers-bucket-list-Athens-Image-1.webp",
                    "is_ai": False
                },
                {
                    "caption": "Paradise found! Crystal clear waters and perfect sunset 🌅 #travel #beach #wanderlust",
                    "image": "aHR0cHM6Ly9waXhwYWNvbS1pbWcucGl4cGEuY29tL2NvbS9hcnRpY2xlcy8xNTI4MTg5NDY4LTkxOTA0OS10aGUtYmVhY2gtMzA1MTY0Ny0xMjgwanBnLmpwZw==.webp",
                    "is_ai": False
                },
                {
                    "caption": "Nature's canvas - the most beautiful landscape I've ever captured 🏔️ #landscape #nature",
                    "image": "a-landscape-image-with-3-by-2-aspect-ratio.webp",
                    "is_ai": False
                }
            ]
        },
        {
            "username": "fitness_coach",
            "email": "fit.coach@example.com",
            "bio": "Certified fitness trainer 💪 | Healthy lifestyle advocate 🥗",
            "profile_pic": "360_F_309111910_oXeV6JhP8nmYPPXLE2E6OXimn9Ot7Bvm.webp",
            "posts": [
                {
                    "caption": "Morning workout routine! 💪 #fitness #health #motivation",
                    "image": "fitness-equipment.webp",
                    "is_ai": False
                },
                {
                    "caption": "Healthy meal prep for the week 🥗 #healthyeating #nutrition",
                    "image": "making-healthy-meal.webp",
                    "is_ai": False
                },
                {
                    "caption": "New equipment arrived! Ready for some intense training 🏋️‍♂️ #gym #fitness",
                    "image": "360_F_309111910_oXeV6JhP8nmYPPXLE2E6OXimn9Ot7Bvm.webp",
                    "is_ai": False
                }
            ]
        },
        {
            "username": "food_blogger",
            "email": "foodie@example.com",
            "bio": "Food lover 🍝 | Recipe creator 👨‍🍳",
            "profile_pic": "delicious-gourmet-food.webp",
            "posts": [
                {
                    "caption": "Homemade Italian pasta 🍝 Recipe in bio! #cooking #foodie",
                    "image": "restaurant-plates.webp",
                    "is_ai": False
                },
                {
                    "caption": "Sunday brunch vibes 🥐☕ #brunch #foodphotography",
                    "image": "green-mimosa-index-67c1ec7f6cdb8.webp",
                    "is_ai": False
                },
                {
                    "caption": "Cooking up something special! 👨‍🍳 #chef #cooking",
                    "image": "shot-of-an-unrecognisable-senior-man-cooking-a-healthy-meal-at-home.webp",
                    "is_ai": False
                }
            ]
        }
    ]

    # Fake accounts with suspicious content
    fake_accounts = [
        {
            "username": "get_rich_quick_247",
            "email": "money.scam@fake.com",
            "bio": "Make $10000 daily! 💰 DM for secret! 🤑",
            "profile_pic": "MM-Money-ScamsFraud.webp",
            "posts": [
                {
                    "caption": "MAKE MONEY FAST!!! 💰💰💰 DM ME NOW!!! #getrich #scam",
                    "image": "cartoon-of-100-dollar-bill-stacks-piled-on-top-of-each-other.webp",
                    "is_ai": True
                },
                {
                    "caption": "Secret money method! Only 100 spots left! 🤑 #pyramid #scheme",
                    "image": "stacks-of-coins.webp",
                    "is_ai": True
                },
                {
                    "caption": "Quit your job today! Join my team! 💵 #mlm #scam",
                    "image": "cash-app-scams-to-watch-out-for.webp",
                    "is_ai": True
                }
            ]
        },
        {
            "username": "fake_luxury_deals",
            "email": "fake.luxury@scam.com",
            "bio": "Cheap luxury items 👜 100% authentic 🤥",
            "profile_pic": "266450-340x219-how-spot-fake-designer-bags.webp",
            "posts": [
                {
                    "caption": "CHEAP GUCCI BAGS!!! 80% OFF!!! #fake #replica",
                    "image": "il_600x600.5780885619_bu54.webp",
                    "is_ai": True
                },
                {
                    "caption": "ROLEX WATCHES FOR $50!!! DM NOW!!! #scam #fake",
                    "image": "longines2.webp",
                    "is_ai": True
                },
                {
                    "caption": "LUXURY CARS AT 90% OFF!!! #counterfeit #cheap",
                    "image": "best_luxury_cars_on_sale.webp",
                    "is_ai": True
                }
            ]
        },
        {
            "username": "crypto_scammer_pro",
            "email": "crypto.scam@fake.com",
            "bio": "Crypto millionaire 🚀 Free money tricks 💰",
            "profile_pic": "Crypto-meme.webp",
            "posts": [
                {
                    "caption": "10000% GUARANTEED RETURNS!!! #crypto #scam #bitcoin",
                    "image": "39.-bitcoin-meme.webp",
                    "is_ai": True
                },
                {
                    "caption": "Send 1 BTC, get 10 BTC back! 🤑 #pyramid #fraud",
                    "image": "mcdonald_bitcoin_crypto_meme_cbd31facb1.webp",
                    "is_ai": True
                },
                {
                    "caption": "Secret crypto method! DM NOW!!! 💰 #scam #crypto",
                    "image": "head-fake-trade.webp",
                    "is_ai": True
                }
            ]
        },
        {
            "username": "fake_giveaway_king",
            "email": "fake.prizes@scam.com",
            "bio": "Daily iPhone giveaway 📱 100% real 🤥",
            "profile_pic": "Fake-Check-by-Gabyjalbert-eplus-GettyImages-172880056-57a694533df78cf45969b4f9.webp",
            "posts": [
                {
                    "caption": "FREE IPHONE 15 GIVEAWAY!!! Just DM credit card! 📱 #scam",
                    "image": "GettyImages-541789136-5795447f3df78c1734ff3d65.webp",
                    "is_ai": True
                },
                {
                    "caption": "WIN PS5!!! Send bank details to enter! 🎮 #fake",
                    "image": "ebayscams_1_new.webp",
                    "is_ai": True
                },
                {
                    "caption": "MACBOOK AIR GIVEAWAY!!! Share password to win! 💻 #scam",
                    "image": "1140x655-perfect-scam-tall.webp",
                    "is_ai": True
                }
            ]
        }
    ]

    # Realistic comments for real accounts
    real_comments = [
        "Beautiful shot! 😍", "This is amazing! ❤️", "Great work! 👏",
        "Love this! ✨", "Incredible photo! 📸", "Thanks for sharing! 🙌",
        "This is inspiring! 💫", "Perfect composition! 👌", "Awesome content! 🔥"
    ]

    # Toxic/spam comments for fake accounts
    toxic_comments = [
        "This is FAKE! 🤬", "SCAMMER ALERT!!! ⚠️", "Reported for spam! 🚫",
        "Total scam account! 😠", "Fake products! Don't trust! ⛔",
        "STOP SCAMMING PEOPLE! 💢", "Reported to authorities! 🚨",
        "This is a BOT! 🤖", "FAKE FAKE FAKE! ❌"
    ]

    # Create real accounts and their posts
    for account in real_accounts:
        user = User(
            username=account["username"],
            email=account["email"],
            is_fake=False,
            profile_pic=account["profile_pic"]
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

        # Create posts for real accounts
        for post_data in account["posts"]:
            post = Post(
                image_path=post_data["image"],
                caption=post_data["caption"],
                user_id=user.id,
                is_ai_generated=post_data["is_ai"]
            )
            db.session.add(post)
            db.session.commit()

            # Add genuine comments and likes
            for _ in range(random.randint(3, 8)):
                comment = Comment(
                    content=random.choice(real_comments),
                    user_id=user.id,
                    post_id=post.id
                )
                db.session.add(comment)

            for _ in range(random.randint(10, 30)):
                like = Like(
                    user_id=user.id,
                    post_id=post.id
                )
                db.session.add(like)

    # Create fake accounts and their posts
    for account in fake_accounts:
        user = User(
            username=account["username"],
            email=account["email"],
            is_fake=True,
            profile_pic=account["profile_pic"]
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

        # Create posts for fake accounts
        for post_data in account["posts"]:
            post = Post(
                image_path=post_data["image"],
                caption=post_data["caption"],
                user_id=user.id,
                is_ai_generated=post_data["is_ai"]
            )
            db.session.add(post)
            db.session.commit()

            # Add toxic comments and suspicious like patterns
            for _ in range(random.randint(5, 12)):
                comment = Comment(
                    content=random.choice(toxic_comments),
                    user_id=user.id,
                    post_id=post.id
                )
                db.session.add(comment)

            # Suspicious pattern of too many likes
            for _ in range(random.randint(50, 100)):
                like = Like(
                    user_id=user.id,
                    post_id=post.id
                )
                db.session.add(like)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables
        
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True,
                profile_pic="20250307093442_GLK_6948.JPG"  # Admin profile picture
            )
            admin.set_password('1234')
            db.session.add(admin)
            db.session.commit()
            
            # Create dummy data
            create_dummy_data()
            
    app.run(debug=True) 