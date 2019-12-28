import os
import requests
from datetime import datetime
from flask import Flask, session, request, render_template, redirect, url_for,jsonify
from flask_session import Session
from passlib.hash import sha256_crypt

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/register/", methods=["GET", "POST"])
def register():
    msg=''
    if request.method =="POST":
        if not request.form.get("username"):
            msg = "must provide username" 
            return render_template("register.html", msg=msg)   
        elif not request.form.get("password"):
            msg = "must provide password"
            return render_template("register.html", msg=msg)
        elif not request.form.get("confirm"):
            msg = "type password again"
            return render_template("register.html", msg=msg)
        elif request.form.get("confirm")!=request.form.get("password"):
            msg = "password and confirmation should match"
            return render_template("register.html", msg=msg)    
        _password = request.form.get("password")
        password = sha256_crypt.hash(_password)
        username = request.form.get("username")  
        x = db.execute("SELECT * FROM users WHERE username = :username",{"username":username})
        if x.rowcount > 0:
            msg="That username is already taken, please choose another"
            return render_template("register.html", msg=msg)

        else:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
                        {"username":username, "password":password})
            db.commit()
                          
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('search'))
       
    return render_template("register.html", msg=msg)

@app.route('/login/', methods=["GET", "POST"])
def login():
    msg=''
    if request.method == 'POST':
        if not request.form.get("username"):
            msg = "must provide username"
            return render_template("login.html", msg=msg)
        if not request.form.get("password"):
            msg = "must provide password"
            return render_template("login.html", msg=msg)
               
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']  
        result = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
        if result is None:
            msg = "invalid credentials"
            return render_template("login.html", msg=msg)
        else:
            password = result['password']    
            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                session['logged_in'] = True
                session['username'] = username
                session['userid'] = result.id
                
                return redirect(url_for('search'))                
            else:
                msg = 'Invalid login'
                return render_template('login.html', msg=msg)
        
    return render_template("login.html", msg=msg)  

@app.route('/search/', methods = ["GET", "POST"])
def search():
    msg=""
    if request.method == 'POST':
        
        isbn = request.form['isbn']
        title = request.form['title']
        author = request.form['author']
        
        
        books = db.execute("SELECT * FROM books WHERE title LIKE :title",{"title": '%' + title + '%'}).fetchall()
        books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn",{"isbn": '%' + isbn + '%'}).fetchall()
        books = db.execute("SELECT * FROM books WHERE title LIKE :title",{"title": '%' + title + '%'}).fetchall()
        
        return render_template("books.html", books=books)
    return render_template('search.html',msg=msg) 

@app.route("/books/<int:book_id>")
def book(book_id):
    """Lists details about a single book."""
    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", msg="No such a book") 
    isbn = book.isbn
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "CveyxirgZiFIJEpPivzJw", "isbns": isbn}) 
    data = res.json()
    avg = float(data['books'][0]['average_rating'])
    num = float(data['books'][0]['work_ratings_count'])   
    session['bookid'] = book.id      
    return render_template("book.html", book=book, avg=avg, num=num) 

@app.route('/review/', methods = ["GET", "POST"])
def review():
    msg=""
    if request.method == 'POST':
        rating = request.form['rate']
        review = request.form['review']
        b_id = session['bookid']
        u_id = session['userid']
        date = datetime.now()
        
       
        db.execute("INSERT INTO reviews (rating, review, b_id, u_id,date) VALUES (:rating, :review, :b_id, :u_id, :date)",
                        {"rating":rating, "review":review, "b_id":b_id, "u_id":u_id, "date":date})
        db.commit()
        return redirect(url_for('book',book_id=b_id))


@app.route('/api/isbn/<int:q_isbn>')
def my_api(q_isbn):
    
    q_isbn = f"%{q_isbn}%".lower()
    book = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn LIMIT 1", {"isbn": q_isbn}).fetchone()
    book_id = book.id
    review = db.execute("SELECT * FROM reviews WHERE b_id = :id",{"id":book_id}).fetchone()
    if book is None:
        return jsonify(
            {
                "error_code": 404,
                "error_message": "Not Found"
            }
        ), 404
    if review is None:
        return jsonify(
            {
                "error_code": 404,
                "error_message": "Not Found"
            }
        ), 404
    
    result = {
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": review.ratings_count,
        "average_score": review.rating
         }
        
    return jsonify(result)  

@app.route("/")
def index():
    return render_template("index.html")
