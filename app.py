import os

from cs50 import SQL
from django.shortcuts import render
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

os.environ.setdefault("API_KEY", "pk_21ecd2eb6d7b457ba1542f31af6488a3")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    transactions = db.execute("SELECT symbol, sum(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
    values = []

    stock_cash = 0

    for i in transactions:
        stock = lookup(i["symbol"])
        stock["shares"] = i["shares"]
        stock["total"] = round(i["shares"] * stock["price"], 2)
        stock_cash += stock["total"]
        values.append(stock)

    user_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])[0]["cash"]

    print(values)

    return render_template("index.html", stocks = values, user_cash = round(user_cash, 2) , total = round(stock_cash + user_cash, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        symbol = request.form.get("symbol")
        shares = None

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares must be a valid number!", 403)

        if not symbol:
            return apology("Must provide a symbol!", 403)

        if not shares:
            return apology("Must provide a number of shares!", 403)

        stock = lookup(symbol.upper())

        if stock is None:

            return apology("Symbol doesn't exist!", 403)

        if shares < 0:
            return apology("Must provide a positive number of shares!", 403)

        spending = stock["price"] * shares

        user_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])[0]["cash"]

        if user_cash < spending:
            return apology("Not enough money!", 403)

        print(f"Spending : {spending}")
        print(f"User Cash : {user_cash}")

        db.execute("UPDATE users SET cash=? WHERE id=?", user_cash - spending, session["user_id"])

        #INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(0, '', 0, 0, '');
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)", session["user_id"], stock["symbol"], shares, stock["price"], datetime.datetime.now())

        flash("Your stock was successfully purchase!")

        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price, date FROM transactions WHERE user_id = ?", session["user_id"])
    values = []

    for i in transactions:
        stock = lookup(i["symbol"])

        if i["shares"] == 0:
            continue

        if i["shares"] < 0:
            i["shares"] = abs(i["shares"])
            i["type"] = "Sold"
            i["total"] = round(i["shares"] * i["price"], 2)
        else:
            i["type"] = "Bought"
            i["total"] = -abs(round(i["shares"] * i["price"], 2))

        

        i["name"] = stock["name"]
        
        values.append(i)

    print(f"HISTORICO : {transactions}")
    return render_template("history.html", stocks = values)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'POST':
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Must give a symbol!", 403)

        stock = lookup(symbol.upper())

        if stock is None:

            return apology("Symbol doesn't exist", 403)

        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"], primaryExchange = stock["primaryExchange"], currency = stock["currency"])

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("confirm_password"):
            return apology("must confurm your password", 403)

        elif request.form.get("confirm_password") != request.form.get("password"):
            return apology("your password doesn't match", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        if len(rows) >= 1:
            return apology("the username already exists", 403)

        user = null

        try:
            user = db.execute("INSERT INTO users(username, hash, cash) VALUES(?,?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")), 10000)
        except:
            return apology("something went wrong", 403)

        # Remember which user has logged in
        session["user_id"] = user

        return redirect("/")
        
    else:
        return render_template("register.html") 


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == 'POST':

        symbol = request.form.get("symbol")
        shares = None

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares must be a valid number!", 403)

        if not symbol:
            return apology("Must provide a symbol!", 403)

        if not shares:
            return apology("Must provide a number of shares!", 403)

        # Information about stock that we wanna sell
        stock = lookup(symbol.upper())

        if stock is None:
            return apology("Symbol doesn't exist!", 403)

        transactions = db.execute("SELECT symbol, sum(shares) as shares FROM transactions WHERE user_id = ? and symbol = ? GROUP BY symbol ;", session["user_id"], stock["symbol"])

        if len(transactions) != 1:
            return apology("You must buy a stock first!", 403)

        if transactions[0]["shares"] < shares:
            return apology("Not enough shares of this stock!", 403)

        user_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])[0]["cash"]
        new_cash = user_cash + stock["price"]

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)", session["user_id"], stock["symbol"], -abs(shares), stock["price"], datetime.datetime.now())
        db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, session["user_id"])

        print(f"TESTE : {transactions}")

        flash(f"Stock sold for ${stock['price']}!")

        return redirect("/")
        
    return render_template("sell.html")

@app.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == 'POST':
        
        if not request.form.get("password"):
            return apology("Must provide a password", 403)

        elif not request.form.get("new_password"):
            return apology("Must provide a new password", 403)

        elif not request.form.get("confirm_new_password"):
            return apology("Must confurm your new password", 403)

        elif request.form.get("new_password") != request.form.get("confirm_new_password"):
            return apology("your new password doesn't match", 403)

        user_password_hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"]

        if check_password_hash(user_password_hash, request.form.get("password")):
            db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(request.form.get("new_password")), session["user_id"])
            return redirect("/")
        else:
            return apology("Wrong password!", 403)

    return render_template("reset-password.html")

def delete_info():
    db.execute('DELETE FROM transactions;')
    db.execute('DELETE FROM users;')

if __name__ == '__main__':
    app.run()