from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, make_response
from flask_session import Session
from tempfile import mkdtemp
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from sqlalchemy import and_
import urllib.request
from urllib.request import urlopen
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import pprint
from GoogleNews import GoogleNews
import nltk
import warnings
warnings.filterwarnings('ignore')
from nltk.sentiment.vader import SentimentIntensityAnalyzer
# nltk.download('vader_lexicon')

#googlenews = GoogleNews()


sia = SentimentIntensityAnalyzer()

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

ENV = 'prod'

if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = ''
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:hamza@localhost/postgres'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # Reject symbol if it contains comma
    if "," in symbol:
        return None

    # Query Alpha Vantage for quote
    # https://www.alphavantage.co/documentation/
    try:

        # GET CSV
        url = f"https://www.alphavantage.co/query?apikey={os.getenv('API_KEY')}&datatype=csv&function=TIME_SERIES_INTRADAY&interval=1min&symbol={symbol}"
        webpage = urllib.request.urlopen(url)

        # Parse CSV
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())

        # Ignore first row
        next(datareader)

        # Parse second row
        row = next(datareader)

        # Ensure stock exists
        try:
            price = float(row[4])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
        return {
            "price": price,
            "symbol": symbol.upper()
        }

    except:
        return None



def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(50))    
    email = db.Column(db.String(50))
    password = db.Column(db.String(50))

    def __init__(self, username, email, password):

        self.username  =   username
        self.email    = email
        self.password = password
    
@app.route("/")
@login_required
def index(): 
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()


    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", message="Please Enter email")
    
        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", message="Please Enter Password")
        
        M_Users = Users.query.filter(and_(Users.username == request.form.get("username"), Users.password ==  request.form.get("password"))).first()
        if M_Users is not None: 
            session['logged_in'] = True
            session["user_id"] = request.form.get("username")
            return redirect(url_for("index")) 
        else: 
            return render_template("login.html", message="Invalid email or password")
    else:
        return render_template("login.html")
   
    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("register.html", message="Please Enter Username")
        elif not request.form.get("password"):
            return render_template("register.html", message="Please Enter Password")
        elif not request.form.get("confirmation"):
            return render_template("register.html", message="Please enter confirmation")   
        elif not request.form.get("email"):
            return render_template("register.html", message="Please enter confirmation")
        username = request.form.get("username")
        password = request.form.get("password") 
        email = request.form.get("email")
        user = Users.query.filter_by(username=username).first()
        if user is not None: 
            return render_template("register.html", message="User already exists")  
        new_user = Users(username, email, password)
        db.session.add(new_user)
        db.session.commit()
        flash("Email successfully registered")

    return render_template("register.html")




@app.route("/news", methods=["GET"])
def news():
    date_sentiments = {}
    if 'id' in request.args:
        id = request.args['id']
    else: 
        return "Error: No id field provided. Please specify an id."

    for i in range(1,3):
        page = urlopen('https://www.businesstimes.com.sg/search/' + str(id) +'?page='+str(i)).read()
        soup = BeautifulSoup(page, features="html.parser")
        posts = soup.findAll("div", {"class": "media-body"})
        for post in posts:
            time.sleep(1)
            url = post.a['href']
            date = post.time.text
            print(date, url)
            try:
                link_page = urlopen(url).read()
            except:
                url = url[:-2]
                link_page = urlopen(url).read()
            link_soup = BeautifulSoup(link_page)
            sentences = link_soup.findAll("p")
            passage = ""
            for sentence in sentences:
                passage += sentence.text
            sentiment = sia.polarity_scores(passage)['compound']
            date_sentiments.setdefault(date, []).append(sentiment)

    date_sentiment = {}

    for k,v in date_sentiments.items():
        date_sentiment[datetime.strptime(k, '%d %b %Y').date() + timedelta(days=1)] = round(sum(v)/float(len(v)),3)
    sum_of_sentiment = 0
    for i in date_sentiment:
        sum_of_sentiment += date_sentiment[i]
    print(sum_of_sentiment)
    
    earliest_date = min(date_sentiment.keys())

    print(date_sentiment)   
    
    return render_template("meter.html", sum_of_sentiment=sum_of_sentiment, id=id)

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect(url_for("index"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        quote = request.form.get("symbol")
        
        return redirect(url_for("news", id=quote))
        
       
    # User reached route via GET (as by clicking a link or via redi)
    else:
        return render_template("quote.html")

