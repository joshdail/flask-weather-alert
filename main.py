from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from forms import SignupForm, LocationForm

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy_utils import database_exists

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user, \
    AnonymousUserMixin

from flask_apscheduler import APScheduler

import requests
import smtplib
import os
from datetime import datetime as dt

API_KEY = os.environ.get("API_KEY")
API_BASE_URL = os.environ.get("API_BASE_URL")

FROM_EMAIL = os.environ.get("FROM_EMAIL")
FROM_PASSWORD = os.environ.get("FROM_PASSWORD")

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
Bootstrap(app)

scheduler = APScheduler()

login_manager = LoginManager()
login_manager.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    alerts = relationship("Alert", back_populates="user")


class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(250), nullable=False)
    alert_time = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = relationship("User", back_populates="alerts")


if not database_exists(DATABASE_URL):
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/", methods=["GET", "POST"])
def home():
    form = SignupForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            # If user already has an account, check password
            if check_password_hash(pwhash=user.password, password=request.form.get('password')):
                login_user(user)
                return redirect(url_for('dashboard', user=user))
            else:
                flash("Password incorrect")
                return render_template('index.html', form=form)
        # If this is a new user, create a new account and redirect to dashboard
        else:
            new_user = User()
            new_user.email = request.form.get("email")
            new_user.password = generate_password_hash(password=request.form.get("password"),
                                                       method='pbkdf2:sha256',
                                                       salt_length=12)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
    return render_template('index.html', form=form)


@login_required
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    form = LocationForm()
    if form.validate_on_submit():
        new_alert = Alert()
        new_alert.location = request.form.get('location')
        new_alert.alert_time = int(request.form.get('alert_time'))
        new_alert.user_id = current_user.id
        new_alert.user = current_user
        db.session.add(new_alert)
        db.session.commit()
    return render_template("dashboard.html", form=form)


@login_required
@app.route("/delete-alert")
def delete_alert():
    alert_id = request.args.get("alert_id")
    alert = Alert.query.get(alert_id)
    if alert.user_id == current_user.id:
        db.session.delete(alert)
        db.session.commit()
    return redirect(url_for('dashboard'))


@login_required
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


# Helper methods for handling the alerts. I'll probably put this in a separate file

def send_alert(weather_data, send_to_email):
    with smtplib.SMTP("smtp.mail.yahoo.com", port=587) as connection:
        message_string = f"Today's weather is expected to be {weather_data['description']}, " \
                         f"with a high of {weather_data['high']} degrees and a low of {weather_data['low']} degrees " \
                         f"Fahrenheit.\n\n" \
                         f"Wind speed is expected to be {weather_data['wind']} mph."
        connection.starttls()
        connection.login(user=FROM_EMAIL, password=FROM_PASSWORD)
        connection.sendmail(from_addr=FROM_EMAIL,
                            to_addrs=send_to_email,
                            msg=f"Subject:Your Morning Weather Report for {dt.now().strftime('%A, %B %I')}\n\n{message_string}")


def get_weather_data(location, send_to_email):
    params = {
        "q": location,
        "appid": API_KEY,
        "units": "imperial"
    }
    res = requests.get(url=API_BASE_URL, params=params)
    res.raise_for_status()
    data = res.json()
    formatted_data = {
        "description": data["weather"][0]["description"],
        "high": data["main"]["temp_min"],
        "low": data["main"]["temp_max"],
        "wind": data["wind"]["speed"]

    }
    send_alert(formatted_data, send_to_email)


def gather_alerts():
    current_hour = dt.now().hour
    print("Checking database for alerts to send...")
    alerts_to_send = Alert.query.filter_by(alert_time=current_hour).all()
    for alert in alerts_to_send:
        get_weather_data(alert.location, alert.user.email)


if __name__ == "__main__":
    scheduler.add_job(id="send alerts", func=gather_alerts, trigger='interval', hours=1)
    scheduler.start()
    app.run(debug=True)
