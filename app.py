import os
import tweepy
from flask import Flask, redirect, request, session, render_template, url_for, flash
from flask_session import Session
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask Setup
app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')  # Get from .env or use default
Session(app)

# Twitter API Keys from environment variables
TWITTER_CLIENT_ID = os.environ.get('TWITTER_API_KEY')
TWITTER_CLIENT_SECRET = os.environ.get('TWITTER_API_SECRET')
TWITTER_CALLBACK_URL = os.environ.get('CALLBACK_URL', 'http://127.0.0.1:5000/callback')

# Check if API keys are available
if not TWITTER_CLIENT_ID or not TWITTER_CLIENT_SECRET:
    print("WARNING: Twitter API credentials not found in environment variables")
    print("Make sure you've created a .env file with TWITTER_API_KEY and TWITTER_API_SECRET")

# Twitter Auth
auth = tweepy.OAuthHandler(TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, TWITTER_CALLBACK_URL)

# 🏠 Home Page
@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))

# 🔑 Twitter Login
@app.route("/login")
def login():
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
        user = api.verify_credentials()
        
        session["user"] = {
            "name": user.name, 
            "screen_name": user.screen_name, 
            "id": user.id, 
            "token": auth.access_token, 
            "token_secret": auth.access_token_secret,
            "profile_image": user.profile_image_url_https
        }
        
        flash(f"Successfully logged in as @{user.screen_name}", "success")
        return redirect(url_for("dashboard"))
    except tweepy.TweepyException as e:
        flash(f"Error! Failed to get access token: {str(e)}", "danger")
        return redirect(url_for("index"))

# 📜 Fetch Tweets
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Please log in to access your dashboard", "warning")
        return redirect(url_for("index"))

    user_data = session["user"]
    auth.set_access_token(user_data["token"], user_data["token_secret"])
    api = tweepy.API(auth)

    try:
        tweets = api.user_timeline(count=10, tweet_mode="extended")  # Get 10 tweets
        return render_template("dashboard.html", tweets=tweets, user=user_data)
    except tweepy.TweepyException as e:
        flash(f"Error fetching tweets: {str(e)}", "danger")
        return render_template("dashboard.html", tweets=[], user=user_data)

# 🗑 Delete Tweet
@app.route("/delete_tweet/<tweet_id>", methods=["POST"])
def delete_tweet(tweet_id):
    if "user" not in session:
        flash("Please log in to delete tweets", "warning")
        return redirect(url_for("index"))

    user_data = session["user"]
    auth.set_access_token(user_data["token"], user_data["token_secret"])
    api = tweepy.API(auth)

    try:
        api.destroy_status(tweet_id)
        flash("Tweet successfully deleted!", "success")
        return redirect(url_for("dashboard"))
    except tweepy.TweepyException as e:
        flash(f"Error deleting tweet: {str(e)}", "danger")
        return redirect(url_for("dashboard"))

# 📝 Create Tweet
@app.route("/create_tweet", methods=["GET", "POST"])
def create_tweet():
    if "user" not in session:
        flash("Please log in to create tweets", "warning")
        return redirect(url_for("index"))
        
    if request.method == "POST":
        tweet_text = request.form.get("tweet_text")
        
        if not tweet_text:
            flash("Tweet text cannot be empty", "danger")
            return redirect(url_for("create_tweet"))
            
        # Add the "posted from kipcodes" signature
        tweet_text += " [posted from kipcodes]"
        
        user_data = session["user"]
        auth.set_access_token(user_data["token"], user_data["token_secret"])
        api = tweepy.API(auth)
        
        try:
            api.update_status(tweet_text)
            flash("Tweet posted successfully!", "success")
            return redirect(url_for("dashboard"))
        except tweepy.TweepyException as e:
            flash(f"Error posting tweet: {str(e)}", "danger")
            return render_template("create_tweet.html")
    
    return render_template("create_tweet.html")

# 🚪 Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))

# Run the app
if __name__ == "__main__":
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Get debug setting from environment variable (default to True for development)
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    app.run(debug=debug, host='0.0.0.0', port=port)