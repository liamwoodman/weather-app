import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # need current holding info
    portfolio = db.execute("SELECT symbol, company, stocks FROM portfolio WHERE userid = :id", id=session["user_id"])
    stockValue = float(0)
    # loop to work out retrieve the stock price and calculate current value of all items of stock in portfolio
    for i in range(len(portfolio)):
        # get API info for each item in portfolio
        ticker = lookup(portfolio[i]["symbol"])
        currentPrice = ticker["price"]
        # add to a list so it can be inserted in the table

        # lookup the amount of stocks held in each item in portfolio
        stocksHeld = int(portfolio[i]["stocks"])
        # calculate the current value of all the stocks held of that item
        value = currentPrice * stocksHeld
        stockValue += value
        portfolio[i].update({'price': currentPrice, 'value': value})
    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cashLeft = cash[0]["cash"]
    overallValue = stockValue + cashLeft
    # need cash balance and total balance
    return render_template("index.html", portfolio=portfolio, stockValue=stockValue, overallValue=overallValue, cashLeft=cashLeft)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # error checking for empty fields and if stock exists
        if not request.form.get("symbol"):
            return apology("Requires symbol to not be blank", 400)
        elif lookup(request.form.get("symbol")) == None:
            return apology("Stock not found", 400)

        # have to do this dang testing to get the check50 off my back (even though the page rejects words)
        floatTest = request.form.get("shares")
        if request.form.get("shares").isalpha():
            return apology("testing", 400)
        elif not floatTest.find(".", 0, len(floatTest)) == -1:
            return apology("test float", 400)
        elif int(request.form.get("shares")) < 1:
            return apology("Please enter a positive number", 400)
        # lookup the symbol
        purchase = lookup(request.form.get("symbol"))
        # WOULD BE NICE IF USERS COULD QUOTE HOW MUCH IT WILL COST THEM - additional feature to add
        # check if the user has enough cash
        userCash = db.execute("SELECT username, cash FROM users WHERE id=:id", id=session["user_id"])
        # if not, apology out
        cost = round((purchase["price"] * int(request.form.get("shares"))))
        if userCash[0]["cash"] < cost:
            return apology("Not enough funds", 400)
        # insert into long-term portfolio db - this is the definitive table where values will be removed
        test = db.execute("INSERT INTO portfolio (userid, username, symbol, company, stocks) VALUES (:userid, :username, :symbol, :company, :stocks)",
                            userid=int(session["user_id"]), username=userCash[0]["username"], symbol=purchase["symbol"], company=purchase["name"],
                            stocks=int(request.form.get("shares")))
        # otherwise insert the purchase into db purchase history db - this will show history
        db.execute("INSERT INTO purchases (username, symbol, company, stocks, cost, userid, buyorsell) VALUES (:username, :symbol, :company, :stocks, :cost, :userid, :buyorsell)"
                    , username=userCash[0]["username"], symbol=purchase["symbol"], company=purchase["name"], stocks=(request.form.get("shares")),
                    cost=(purchase["price"] * int(request.form.get("shares"))), userid=session["user_id"], buyorsell="buy")
        # remove from balance
        purchaseSuccess = db.execute("UPDATE users SET cash = (cash - :cost) WHERE id=:id", cost=cost, id=session["user_id"])
        # return values for how much it cost the user so it can be displayed in a table
        return redirect("/")
        #return render_template("buy.html", purchaseSuccess = purchaseSuccess, purchase = purchase, cost = cost)

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET", "POST"])
def check():
    """Return true if username available, else false, in JSON format"""
    un = request.args.get("un")
    userLookup = db.execute("SELECT username FROM users WHERE username=:username", username=un)
    if userLookup:
        return jsonify("True")
    elif userLookup == None:
        return jsonify("False")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    purchases = db.execute("SELECT symbol, company, stocks, cost, buyorsell, datetime FROM purchases WHERE userid=:id", id=session["user_id"])
    return render_template("history.html", purchases=purchases)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username=:username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    if request.method == "POST":
        # check if the stock symbol is not empty
        if not request.form.get("symbol"):
            return apology("Must enter stock symbol", 400)
        # take value and check against API
        userSymbol = request.form.get("symbol")
        results = lookup(userSymbol)
        if results == None:
            return apology("Symbol not found", 400)
        else:
            return render_template("/quote.html", results=results)

    else:
        return render_template("/quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # if the details are being posted
    if request.method == "POST":
        # ensure username was given AND ---
        # testing = db.execute("SELECT username FROM users WHERE username = :username", username = request.form.get('username'))
        # print(request.form.get('username'))
        # print(f"{testing}")

        usernameCheck = db.execute("SELECT username FROM users WHERE username=:username", username=request.form.get('username'))
        # checking if they have given username
        if not request.form.get('username'):
            return apology("Must provide username", 400)
        # if a username is found, return that its taken
        elif not usernameCheck == []:
            return apology("That username is taken", 400)
        # ensure password was entered
        elif not request.form.get('password'):
            return apology("Must provide password", 400)
        # ensure password confirmation is matching confirmation or not blank
        elif not request.form.get('confirmation') or not request.form.get('confirmation') == request.form.get('password'):
            return apology("Must provide matching password", 400)
        # if all is hunky dory, insert into database
        else:
            registerUser = request.form.get('username')
            registerPassHash = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256', salt_length=8)
            registered = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                                    username=request.form.get('username'), hash=generate_password_hash
                                    (request.form.get('password'), method='pbkdf2:sha256', salt_length=8))

        # now send user back to login page
        return render_template("login.html", registered=registered)
    # if the user goes to register by mistake
    else:
        return render_template("/register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # change this to query the portfolio db
    portfolio = db.execute("SELECT sid, symbol, company, stocks FROM portfolio WHERE userid=:id", id=session["user_id"])
    stockValue = float(0)
    # code taken from index page to display, refer to this for notation
    for i in range(len(portfolio)):
        ticker = lookup(portfolio[i]["symbol"])
        currentPrice = ticker["price"]
        stocksHeld = int(portfolio[i]["stocks"])
        value = currentPrice * stocksHeld
        stockValue += value
        portfolio[i].update({'price': currentPrice, 'value': value})

# Submit the user’s input via POST to /sell.
    if request.method == "POST":
        stocks = request.form.get("symbol")
        # check if its a default value and return false - need to do an if to double check they have that stock - but seems redundant
        # given page pre-renders with all held stocks.
        if not stocks:
            return apology("Please select a stock", 400)
        # check 50 testing
        floatTest = request.form.get("shares")
        if request.form.get("shares").isalpha():
            return apology("Please enter an integer", 400)
        elif not floatTest.find(".", 0, len(floatTest)) == -1:
            return apology("Please enter a whole number", 400)
        elif int(request.form.get("shares")) < 1:
            return apology("Please enter a positive number", 400)

        # redone this to find the ID of the initial purchase
        stocksId = int(stocks[0:stocks.find(".")])
        # check number of shares they want to sell
        stocksSelling = int(request.form.get("shares"))
        if stocksSelling <= 0:
            return apology("Select a number of shares greater than zero to sell", 400)
        # pull out of our string how many stocks they want to sell
        stocksAmount = int(stocks[stocks.find(":") + 2:stocks.find("s")].strip())
        if stocksAmount < stocksSelling:
            return apology("You do not have that many stocks", 400)
        # lookup from portfolio db
        toSell = db.execute("SELECT username, symbol, company, stocks FROM portfolio WHERE sid=:sid", sid=stocksId)
        sellPrice = lookup(toSell[0]["symbol"])
        # remove from portfolio db either fully or decrease by amount
        if stocksSelling == stocksAmount:
            db.execute("DELETE FROM portfolio WHERE sid=:sid", sid=stocksId)
        elif stocksSelling < stocksAmount:
            db.execute("UPDATE portfolio SET stocks = (stocks - :stocks) WHERE sid=:sid", stocks=stocksSelling, sid=stocksId)

        # insert into purchases db but coding that it's a sale
        db.execute("INSERT INTO purchases (username, symbol, company, stocks, cost, userid, buyorsell) VALUES (:username, :symbol, :company, :stocks, :cost, :userid, :buyorsell)", username=toSell[0]["username"], symbol=toSell[0]["symbol"], company=toSell[0]["company"], stocks=stocksSelling,
                    cost=(sellPrice["price"] * stocksSelling), userid=session["user_id"], buyorsell="sel")
        # add money back to cash column in Users
        db.execute("UPDATE users SET cash=(cash + :sale) WHERE id=:id", sale=(sellPrice["price"] * int(toSell[0]["stocks"])),
                    id=session["user_id"])

        # update the sell block
        portfolio = db.execute("SELECT sid, symbol, company, stocks FROM portfolio WHERE userid = :id", id=session["user_id"])
        stockValue = float(0)
        # code taken from index page to display, refer to this for notation
        for i in range(len(portfolio)):
            ticker = lookup(portfolio[i]["symbol"])
            currentPrice = ticker["price"]
            stocksHeld = int(portfolio[i]["stocks"])
            value = currentPrice * stocksHeld
            stockValue += value
            portfolio[i].update({'price': currentPrice, 'value': value})

        return render_template("/sell.html", toSell=toSell, portfolio=portfolio)

    else:
        return render_template("/sell.html", portfolio=portfolio)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
