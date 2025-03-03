import os
import tweepy
from flask import Flask, redirect, request, session, render_template, url_for, flash
from flask_session import Session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask Setup
app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')
Session(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# Twitter API Keys from environment variables
TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY')
TWITTER_API_SECRET = os.environ.get('TWITTER_API_SECRET')
TWITTER_CALLBACK_URL = os.environ.get('CALLBACK_URL', 'http://127.0.0.1:5000/callback')

# Check if API keys are available
if not TWITTER_API_KEY or not TWITTER_API_SECRET:
    print("WARNING: Twitter API credentials not found in environment variables")
    print("Make sure you've created a .env file with TWITTER_API_KEY and TWITTER_API_SECRET")

# Twitter Auth
auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_CALLBACK_URL)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["id"])  # Convert to string for Flask-Login
        self.name = user_data["name"]
        self.screen_name = user_data["screen_name"]
        self.profile_image = user_data.get("profile_image", "")
        self.token = user_data["token"]
        self.token_secret = user_data["token_secret"]
        self.data = user_data  # Store all data for convenience

    def get_id(self):
        return self.id

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    if "user" in session and str(session["user"]["id"]) == user_id:
        return User(session["user"])
    return None

# Helper function to get Twitter API for current user
def get_twitter_api():
    auth.set_access_token(current_user.token, current_user.token_secret)
    return tweepy.API(auth)

# 🏠 Home Page
@app.route("/")
def index():
    return render_template("index.html")

# 🔑 Twitter Login
@app.route("/login")
def login():
    # Clear any existing session
    session.clear()
    
    try:
        redirect_url = auth.get_authorization_url()
        session["request_token"] = auth.request_token
        return redirect(redirect_url)
    except tweepy.TweepyException as e:
        flash(f"Error! Unable to authenticate: {str(e)}", "danger")
        return redirect(url_for("index"))

# 🔄 Callback (Handle OAuth Response)
@app.route("/callback")
def callback():
    request_token = session.pop("request_token", None)
    
    if not request_token:
        flash("Authentication failed: No request token found", "danger")
        return redirect(url_for("index"))
    
    auth.request_token = request_token
    verifier = request.args.get("oauth_verifier")

    if not verifier:
        flash("Authentication failed: No verifier code received", "danger")
        return redirect(url_for("index"))

    try:
        auth.get_access_token(verifier)
        api = tweepy.API(auth)
        twitter_user = api.verify_credentials()
        
        # Store user info in session
        user_data = {
            "id": twitter_user.id,
            "name": twitter_user.name, 
            "screen_name": twitter_user.screen_name, 
            "profile_image": twitter_user.profile_image_url_https,
            "token": auth.access_token, 
            "token_secret": auth.access_token_secret
        }
        
        session["user"] = user_data
        
        # Create Flask-Login user and log them in
        user = User(user_data)
        login_user(user)
        
        flash(f"Successfully logged in as @{twitter_user.screen_name}", "success")
        return redirect(url_for("dashboard"))
    except tweepy.TweepyException as e:
        flash(f"Error! Failed to get access token: {str(e)}", "danger")
        return redirect(url_for("index"))

# 📜 Fetch Tweets
@app.route("/dashboard")
@login_required
def dashboard():
    try:
        api = get_twitter_api()
        # Get user's tweets - tweet_mode="extended" for full text
        tweets = api.user_timeline(count=10, tweet_mode="extended")
        return render_template("dashboard.html", tweets=tweets)
    except tweepy.TweepyException as e:
        flash(f"Error fetching tweets: {str(e)}", "danger")
        return render_template("dashboard.html", tweets=[])

# 🗑 Delete Tweet
@app.route("/delete_tweet/<tweet_id>", methods=["POST"])
@login_required
def delete_tweet(tweet_id):
    try:
        api = get_twitter_api()
        api.destroy_status(tweet_id)
        flash("Tweet successfully deleted!", "success")
    except tweepy.TweepyException as e:
        flash(f"Error deleting tweet: {str(e)}", "danger")
    
    return redirect(url_for("dashboard"))

# 📝 Create Tweet
@app.route("/create_tweet", methods=["GET", "POST"])
@login_required
def create_tweet():
    if request.method == "POST":
        tweet_text = request.form.get("tweet_text")
        
        if not tweet_text:
            flash("Tweet text cannot be empty", "danger")
            return redirect(url_for("create_tweet"))
            
        # Add the "posted from kipcodes" signature
        tweet_text += " [posted from kipcodes]"
        
        try:
            api = get_twitter_api()
            api.update_status(tweet_text)
            flash("Tweet posted successfully!", "success")
            return redirect(url_for("dashboard"))
        except tweepy.TweepyException as e:
            flash(f"Error posting tweet: {str(e)}", "danger")
            return render_template("create_tweet.html")
    
    return render_template("create_tweet.html")

# 🖋 Edit Tweet (Delete and Repost)
@app.route("/edit_tweet/<tweet_id>", methods=["GET", "POST"])
@login_required
def edit_tweet(tweet_id):
    api = get_twitter_api()
    
    # For GET requests, fetch the tweet text
    if request.method == "GET":
        try:
            tweet = api.get_status(tweet_id, tweet_mode="extended")
            # Remove the "posted from kipcodes" suffix if present
            tweet_text = tweet.full_text
            if " [posted from kipcodes]" in tweet_text:
                tweet_text = tweet_text.replace(" [posted from kipcodes]", "")
            elif " [edited via kipcodes]" in tweet_text:
                tweet_text = tweet_text.replace(" [edited via kipcodes]", "")
                
            return render_template("edit_tweet.html", tweet_id=tweet_id, tweet_text=tweet_text)
        except tweepy.TweepyException as e:
            flash(f"Error retrieving tweet: {str(e)}", "danger")
            return redirect(url_for("dashboard"))
    
    # For POST requests, update the tweet
    elif request.method == "POST":
        new_text = request.form.get("tweet_text")
        
        if not new_text:
            flash("Tweet text cannot be empty", "danger")
            return redirect(url_for("edit_tweet", tweet_id=tweet_id))
        
        # Add edited signature
        new_text += " [edited via kipcodes]"
        
        try:
            # Delete the original tweet
            api.destroy_status(tweet_id)
            
            # Post the new tweet
            api.update_status(new_text)
            
            flash("Tweet updated successfully!", "success")
            return redirect(url_for("dashboard"))
        except tweepy.TweepyException as e:
            flash(f"Error updating tweet: {str(e)}", "danger")
            return redirect(url_for("dashboard"))

# 🚪 Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))

# 🗑️ Batch Delete Tweets
@app.route("/batch_delete", methods=["POST"])
@login_required
def batch_delete():
    tweet_ids = request.form.getlist("tweet_ids")
    
    if not tweet_ids:
        flash("No tweets selected for deletion", "warning")
        return redirect(url_for("dashboard"))
    
    api = get_twitter_api()
    success_count = 0
    error_count = 0
    
    for tweet_id in tweet_ids:
        try:
            api.destroy_status(tweet_id)
            success_count += 1
        except tweepy.TweepyException:
            error_count += 1
    
    if success_count:
        flash(f"Successfully deleted {success_count} tweets", "success")
    if error_count:
        flash(f"Failed to delete {error_count} tweets", "warning")
    
    return redirect(url_for("dashboard"))

# Run the app
if __name__ == "__main__":
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Get debug setting from environment variable (default to True for development)
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    app.run(debug=debug, host='0.0.0.0', port=port)