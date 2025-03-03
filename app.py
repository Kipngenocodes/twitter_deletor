import os
import tweepy
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

from config import Config
from models import db, User, Tweet

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Twitter API setup
def get_twitter_auth():
    auth = tweepy.OAuthHandler(
        app.config['TWITTER_API_KEY'],
        app.config['TWITTER_API_SECRET'],
        app.config['TWITTER_CALLBACK_URL']
    )
    return auth

def get_twitter_api(access_token, access_token_secret):
    auth = get_twitter_auth()
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    auth = get_twitter_auth()
    try:
        redirect_url = auth.get_authorization_url()
        session['request_token'] = auth.request_token
        return redirect(redirect_url)
    except tweepy.TweepyException as e:
        flash(f'Error: Failed to get request token. {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/callback')
def callback():
    # Get the request token
    request_token = session.get('request_token')
    if not request_token:
        flash('Authentication failed. Please try again.', 'danger')
        return redirect(url_for('index'))
    
    auth = get_twitter_auth()
    auth.request_token = request_token
    
    # Get the verifier
    verifier = request.args.get('oauth_verifier')
    if not verifier:
        flash('Authentication failed. Please try again.', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Get the access token
        auth.get_access_token(verifier)
        access_token = auth.access_token
        access_token_secret = auth.access_token_secret
        
        # Get the user information
        api = tweepy.API(auth)
        twitter_user = api.verify_credentials()
        
        # Check if the user exists in our database
        user = User.query.filter_by(twitter_id=str(twitter_user.id)).first()
        
        if not user:
            # Create a new user
            user = User(
                twitter_id=str(twitter_user.id),
                username=twitter_user.screen_name,
                display_name=twitter_user.name,
                profile_image=twitter_user.profile_image_url_https,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            db.session.add(user)
        else:
            # Update existing user
            user.username = twitter_user.screen_name
            user.display_name = twitter_user.name
            user.profile_image = twitter_user.profile_image_url_https
            user.access_token = access_token
            user.access_token_secret = access_token_secret
            user.last_login = datetime.utcnow()
        
        db.session.commit()
        login_user(user)
        
        # Store access tokens in session for easy API access
        session['access_token'] = access_token
        session['access_token_secret'] = access_token_secret
        
        flash('Login successful!', 'success')
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        flash(f'Error during authentication: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get user's tweets
        api = get_twitter_api(
            session.get('access_token'),
            session.get('access_token_secret')
        )
        
        # Fetch tweets with pagination support
        page = request.args.get('page', 1, type=int)
        count = 20  # Tweets per page
        
        if page == 1:
            tweets = api.user_timeline(count=count, tweet_mode='extended')
        else:
            # Get the max_id from the oldest tweet from the previous page
            oldest_tweet_id = session.get('oldest_tweet_id')
            if oldest_tweet_id:
                tweets = api.user_timeline(
                    count=count, 
                    max_id=oldest_tweet_id - 1,
                    tweet_mode='extended'
                )
            else:
                tweets = []
        
        # Store the oldest tweet ID for pagination
        if tweets:
            session['oldest_tweet_id'] = tweets[-1].id
        
        return render_template('dashboard.html', tweets=tweets, page=page)
    
    except tweepy.TweepyException as e:
        flash(f'Error fetching tweets: {str(e)}', 'danger')
        return render_template('dashboard.html', tweets=[])

@app.route('/create-tweet', methods=['GET', 'POST'])
@login_required
def create_tweet():
    if request.method == 'POST':
        text = request.form.get('text')
        
        if not text:
            flash('Tweet text cannot be empty.', 'danger')
            return redirect(url_for('create_tweet'))
        
        try:
            api = get_twitter_api(
                session.get('access_token'),
                session.get('access_token_secret')
            )
            
            # Post the tweet
            tweet = api.update_status(text + " [posted from kipcodes]")
            
            # Store in our database
            db_tweet = Tweet(
                twitter_id=str(tweet.id),
                user_id=current_user.id,
                text=text
            )
            db.session.add(db_tweet)
            db.session.commit()
            
            flash('Tweet posted successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        except tweepy.TweepyException as e:
            flash(f'Error posting tweet: {str(e)}', 'danger')
            return redirect(url_for('create_tweet'))
    
    return render_template('tweet_form.html', action='create')

@app.route('/delete-tweet/<tweet_id>', methods=['POST'])
@login_required
def delete_tweet(tweet_id):
    try:
        api = get_twitter_api(
            session.get('access_token'),
            session.get('access_token_secret')
        )
        
        # Delete the tweet
        api.destroy_status(tweet_id)
        
        # Remove from our database if it exists
        tweet = Tweet.query.filter_by(twitter_id=tweet_id).first()
        if tweet:
            db.session.delete(tweet)
            db.session.commit()
        
        flash('Tweet deleted successfully!', 'success')
    except tweepy.TweepyException as e:
        flash(f'Error deleting tweet: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/edit-tweet/<tweet_id>', methods=['GET', 'POST'])
@login_required
def edit_tweet(tweet_id):
    # Note: Twitter API doesn't allow directly editing tweets
    # We'll delete the old one and post a new one
    
    try:
        api = get_twitter_api(
            session.get('access_token'),
            session.get('access_token_secret')
        )
        
        # Get the original tweet
        tweet = api.get_status(tweet_id, tweet_mode='extended')
        original_text = tweet.full_text
        
        if request.method == 'POST':
            new_text = request.form.get('text')
            
            if not new_text:
                flash('Tweet text cannot be empty.', 'danger')
                return redirect(url_for('edit_tweet', tweet_id=tweet_id))
            
            # Delete the old tweet
            api.destroy_status(tweet_id)
            
            # Post the new tweet
            new_tweet = api.update_status(new_text + " [edited via kipcodes]")
            
            # Update in our database
            db_tweet = Tweet.query.filter_by(twitter_id=tweet_id).first()
            if db_tweet:
                db_tweet.twitter_id = str(new_tweet.id)
                db_tweet.text = new_text
                db.session.commit()
            
            flash('Tweet updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        # Remove any "posted from" suffix that might exist
        if " [posted from kipcodes]" in original_text:
            original_text = original_text.replace(" [posted from kipcodes]", "")
        elif " [edited via kipcodes]" in original_text:
            original_text = original_text.replace(" [edited via kipcodes]", "")
        
        return render_template('tweet_form.html', action='edit', tweet_id=tweet_id, text=original_text)
    
    except tweepy.TweepyException as e:
        flash(f'Error editing tweet: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    tweet_ids = request.form.getlist('tweet_ids')
    
    if not tweet_ids:
        flash('No tweets selected for deletion.', 'warning')
        return redirect(url_for('dashboard'))
    
    api = get_twitter_api(
        session.get('access_token'),
        session.get('access_token_secret')
    )
    
    success_count = 0
    error_count = 0
    
    for tweet_id in tweet_ids:
        try:
            api.destroy_status(tweet_id)
            
            # Remove from our database if it exists
            tweet = Tweet.query.filter_by(twitter_id=tweet_id).first()
            if tweet:
                db.session.delete(tweet)
            
            success_count += 1
        except tweepy.TweepyException:
            error_count += 1
    
    db.session.commit()
    
    if success_count > 0:
        flash(f'Successfully deleted {success_count} tweets.', 'success')
    if error_count > 0:
        flash(f'Failed to delete {error_count} tweets.', 'warning')
    
    return redirect(url_for('dashboard'))

# Initialize the database
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)