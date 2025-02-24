import os
import tweepy
from flask import Flask, redirect, request, session, render_template, url_for
from flask_session import Session

# Flask Setup
app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = "supersecretkey"
Session(app)

# Twitter API Keys (Replace with your credentials)
TWITTER_CLIENT_ID = "your_client_id"
TWITTER_CLIENT_SECRET = "your_client_secret"
TWITTER_BEARER_TOKEN = "your_bearer_token"
CALLBACK_URL = "http://127.0.0.1:5000/callback"

# Twitter Auth
auth = tweepy.OAuthHandler(TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, CALLBACK_URL)

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
    except tweepy.TweepError:
        return "Error! Unable to authenticate."

# 🔄 Callback (Handle OAuth Response)
@app.route("/callback")
def callback():
    request_token = session.pop("request_token", None)
    auth.request_token = request_token
    verifier = request.args.get("oauth_verifier")

    try:
        auth.get_access_token(verifier)
        api = tweepy.API(auth)
        user = api.me()
        session["user"] = {"name": user.name, "screen_name": user.screen_name, "id": user.id, "token": auth.access_token, "token_secret": auth.access_token_secret}
        return redirect(url_for("dashboard"))
    except tweepy.TweepError:
        return "Error! Failed to get access token."

# 📜 Fetch Tweets
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("index"))

    user_data = session["user"]
    auth.set_access_token(user_data["token"], user_data["token_secret"])
    api = tweepy.API(auth)

    tweets = api.user_timeline(count=10, tweet_mode="extended")  # Get 10 tweets
    return render_template("dashboard.html", tweets=tweets, user=user_data)

# 🗑 Delete Tweet
@app.route("/delete_tweet/<tweet_id>", methods=["POST"])
def delete_tweet(tweet_id):
    if "user" not in session:
        return redirect(url_for("index"))

    user_data = session["user"]
    auth.set_access_token(user_data["token"], user_data["token_secret"])
    api = tweepy.API(auth)

    try:
        api.destroy_status(tweet_id)
        return redirect(url_for("dashboard"))
    except Exception as e:
        return f"Error deleting tweet: {e}"

# 🚪 Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
