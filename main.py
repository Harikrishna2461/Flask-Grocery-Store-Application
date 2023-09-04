import os
from io import BytesIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from flask import Flask, request, render_template, flash, redirect, url_for, session, jsonify, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS  # Import the CORS extension
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px

#import logging
#import jinja2  #Not needed if we are using Flask because Flask already uses Jinja2 to render the templates.

port = int(os.environ.get('PORT', 5000))

app = Flask(__name__,
            template_folder="templates",
            static_url_path="/static_folder")
# Setting up CORS to handle headers for all responses
CORS(app)
# Create a CSRF protected form to use the CSRF token
#csrf = CSRFProtect(app)
#Setting our secret key.
app.config['SECRET_KEY'] = 'Hari_3862'

# Configure Flask-Session to use filesystem-based session storage
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize the session
Session(app)
#Inititalizing the SQLLite Engine.
database_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'grocery_store_database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///grocery_store_database.db'

database = SQLAlchemy(app)

#We use the LoginManager in our app for handling user authentication and user session management.
login_manager = LoginManager(app)
login_manager.login_view = 'user_login'


#First Let us Define the Tables.
class Category(database.Model):
  ID = database.Column(database.Integer,
                       primary_key=True,
                       autoincrement=True,
                       nullable=False)
  CATEGORY_NAME = database.Column(database.String(50),
                                  unique=True,
                                  nullable=False)

  #We define the following function because when we print an object of this class,it should'nt print some pointer
  #but should print out the name of that object belonging to this class.
  #def __repr__(self):
  #     return self.name


class Products(database.Model):
  ID = database.Column(database.Integer,
                       primary_key=True,
                       autoincrement=True,
                       nullable=False)
  Name = database.Column(database.String(100), unique=True, nullable=False)
  Price = database.Column(database.Float, nullable=False)
  Quantity_Available = database.Column(database.Integer, nullable=False)
  Category_ID = database.Column(database.Integer, nullable=False)
  Unit = database.Column(database.String(10), nullable=False)


  #def __repr__(self):
  #return self.name
class CartHistory(database.Model):

  order_id = database.Column(database.Integer,
                             primary_key=True,
                             autoincrement=True)
  #product_id = database.Column(database.Integer,
  #nullable=False)
  product_name = database.Column(database.String(20), nullable=False)
  quantity = database.Column(database.Integer, nullable=False)
  order_date = database.Column(DateTime, nullable=False)

  #def __init__(self, order_id, product_name, quantity, order_date):
  #self.product_name = product_name
  #self.quantity = quantity
  #self.order_date = order_date


class Users(UserMixin, database.Model):
  ID = database.Column(database.Integer,
                       primary_key=True,
                       autoincrement=True,
                       nullable=False)
  Username = database.Column(database.String(50), unique=True, nullable=False)
  Email_ID = database.Column(database.String(100), unique=True, nullable=False)
  Hashed_Password = database.Column(
    database.String(128),
    nullable=False)  # Use 128 characters for the hashed password
  Usertype = database.Column(database.String(20), nullable=False)

  def generate_hashed_password(self, password):
    self.Hashed_Password = generate_password_hash(password)

  def check_password_existence(self, password):
    return check_password_hash(self.Hashed_Password, password)

  def is_active(self):
    #We assume all users are active. Modify this based on your actual logic.
    return True

  # Required by Flask-Login to get a unique identifier for the user.
  def get_id(self):
    return str(self.ID)


#This is used to retrieve a user object based on the user ID stored in the session. and this returns None if the User is not found.
@login_manager.user_loader
def Load_User(user_ID):
  return Users.query.get(int(user_ID))


def get_current_user():
  return current_user


#Defining our App Routes.
# Initialize the cart_items dictionary to store cart items in memory
cart_items = {}


@app.route('/products_home', methods=['GET', 'POST'])
#@login_required
def products_home():
  global cart_items  # Use the global cart_items dictionary

  # Fetch filter parameters from request.args
  price_filter = request.args.get('price_filter')
  quantity_filter = request.args.get('quantity_filter')
  category_filter = request.args.get('category_filter')
  if request.method == 'POST':
    search_query = request.form.get('search_query')
  else:
    search_query = request.args.get('search_query')

  # Fetch all products and categories
  products_query = Products.query
  categories = Category.query.all()

  # Apply filters based on the filter parameters
  if category_filter and category_filter != 'all':
    products_query = products_query.filter(
      Products.Category_ID == int(category_filter))

  if price_filter == 'low_to_high':
    products_query = products_query.order_by(Products.Price.asc())
  elif price_filter == 'high_to_low':
    products_query = products_query.order_by(Products.Price.desc())

  if quantity_filter == 'low_to_high':
    products_query = products_query.order_by(Products.Quantity_Available.asc())
  elif quantity_filter == 'high_to_low':
    products_query = products_query.order_by(
      Products.Quantity_Available.desc())

  if search_query:
    products_query = products_query.filter(
      Products.Name.ilike(f"%{search_query}%"))

  products = products_query.all()

  # Handle form submissions to add products to the cart
  if request.method == 'POST':
    product_id = request.form.get('product_id')
    quantity = request.form.get('quantity')
    try:
      quantity = int(quantity) if quantity else 0
    except ValueError:
      quantity = 0

    # Validate the product_id and quantity
    if product_id is None or quantity is None or quantity <= 0:
      flash('Invalid product or quantity.', 'error')
    else:
      # Get the product based on the product_id
      product = Products.query.get(product_id)

      if product:
        # Check if the product is already in the cart
        if product_id in cart_items:
          cart_items[product_id] += quantity
        else:
          cart_items[product_id] = quantity

        # Validate the cart quantity against Quantity_Available
        if cart_items[product_id] > product.Quantity_Available:
          flash(
            f"Sorry, we don't have the requested quantity of {product.Name}.",
            'error')
          cart_items[product_id] = product.Quantity_Available

        flash('Product added to cart successfully.', 'success')
      else:
        flash(f"Product with ID {product_id} not found.", 'error')

    # Redirect to the same page after adding the product to the cart
    return redirect(
      url_for('products_home',
              products=products,
              price_filter=price_filter,
              quantity_filter=quantity_filter,
              category_filter=category_filter,
              search_query=search_query))

  return render_template('products_home.html',
                         products=products,
                         categories=categories,
                         price_filter=price_filter,
                         quantity_filter=quantity_filter,
                         category_filter=category_filter,
                         search_query=search_query)


@app.route('/cart', methods=['GET', 'POST'])
#@login_required
def cart():
  global cart_items  # Use the global cart_items dictionary

  # Retrieve the product details from the cart_items dictionary
  product_ids = [int(product_id) for product_id in cart_items.keys()]
  products = Products.query.filter(Products.ID.in_(product_ids)).all()
  #products = Products.query.filter(Products.ID.in_(cart_items.keys())).all()
  cart_items_list = []

  for product in products:
    quantity = cart_items[str(product.ID)]
    subtotal = product.Price * quantity
    cart_items_list.append({
      'product': product,
      'quantity': quantity,
      'subtotal': subtotal
    })

  return render_template('cart.html', cart_items=cart_items_list)


@app.route('/buy', methods=['GET', 'POST'])
def buy():
  global cart_items

  for product_id, quantity in cart_items.items():
    product = Products.query.get(product_id)
    if product:
      if quantity <= product.Quantity_Available:
        # Update the product Quantity_Available in the database
        product.Quantity_Available -= quantity
        #Setting our order ID
        order_id = CartHistory.query.with_entities(func.count()).scalar() + 1
        # Move the cart item to the cart_history table
        cart_history_item = CartHistory(product_name=product.Name,
                                        quantity=quantity,
                                        order_date=datetime.utcnow())
        database.session.add(cart_history_item)

      else:
        flash(
          f"Sorry, we don't have the requested quantity of {product.Name}.",
          'error')
        return redirect(url_for('cart'))

  # Commit changes to the database after all cart items are processed
  database.session.commit()

  # Clear the cart_items dictionary after successful purchase
  cart_items = {}
  flash('Items bought successfully!', 'success')
  return render_template('buy.html')


# New Admin Home Page for Managers/Admins
@app.route('/admin_home')
#@login_required
def admin_home():
  categories = Category.query.all()
  products = Products.query.all()
  return render_template('admin_home.html',
                         categories=categories,
                         products=products)


#Now we define the Admin Page Funtions.
# Route to add a new category (form)
@app.route('/add_new_category', methods=['GET', 'POST'])
def add_new_category():
  if request.method == 'POST':
    category_id = request.form.get('category_id')
    category_name = request.form.get('category_name')

    # Validate that both category_id and category_name are provided
    if not category_id or not category_name:
      flash('Both Category ID and Category Name are required.', 'error')
    else:
      # Check if the category_id is unique
      existing_category = Category.query.filter_by(ID=category_id).first()
      if existing_category:
        flash(
          f'Category ID {category_id} already exists. Please choose a different ID.',
          'error')
      else:
        # Add the new category to the database
        new_category = Category(ID=category_id, CATEGORY_NAME=category_name)
        database.session.add(new_category)
        database.session.commit()
        flash(f'Category {category_name} added successfully.', 'success')

  return render_template('add_new_category.html')


@app.route('/delete_category', methods=['GET', 'POST'])
def delete_category():
  if request.method == 'POST':
    category_id = request.form['category_id']

    # Check if the category exists
    category = Category.query.get(category_id)
    if category:
      database.session.delete(category)
      database.session.commit()
      flash(
        f"Category '{category.CATEGORY_NAME}' with ID '{category.ID}' has been deleted successfully.",
        'success')
    else:
      flash(f"Category with ID '{category_id}' does not exist.", 'error')

    return redirect(url_for('admin_home'))

  # If it's a GET request, render the "delete_category.html" template
  return render_template('delete_category.html',
                         categories=Category.query.all())


@app.route('/update_category', methods=['GET', 'POST'])
def update_category():
  if request.method == 'POST':
    category_id = request.form['category_id']
    new_category_name = request.form['new_category_name']
    new_category_id = request.form['new_category_id']

    # Check if the category exists
    category = Category.query.get(category_id)
    if category:
      category.CATEGORY_NAME = new_category_name
      category.CATEGORY_ID = new_category_id
      database.session.commit()
      flash(
        f"Category with ID '{category.ID}' has been updated with the new name '{new_category_name}'.",
        'success')
    else:
      flash(f"Category with ID '{category_id}' does not exist.", 'error')

    return redirect(url_for('admin_home'))

  # If it's a GET request, render the "update_category.html" template
  return render_template('update_category.html',
                         categories=Category.query.all())


# Add Product Route
@app.route('/add_new_products', methods=['GET', 'POST'])
#@login_required
def add_new_products():
  #if not current_user.is_authenticated or current_user.Usertype != 'admin':
  # flash('You do not have permission to add products.', 'error')
  # return redirect(url_for('admin_home'))
  if request.method == 'POST':
    name = request.form['name']
    price = float(request.form['price'])
    quantity_available = int(request.form['quantity_available'])
    category_id = int(request.form['category_id'])
    unit = request.form['unit']

    product = Products(Name=name,
                       Price=price,
                       Quantity_Available=quantity_available,
                       Category_ID=category_id,
                       Unit=unit)
    database.session.add(product)
    database.session.commit()

    flash('Product added successfully.', 'success')
    return redirect(url_for('admin_home'))

  categories = Category.query.all()
  return render_template('add_new_products.html', categories=categories)


# Update Product Route
@app.route('/update_existing_product/<int:product_id>',
           methods=['GET', 'POST'])
#@login_required
def update_existing_product(product_id):
  product = Products.query.get_or_404(product_id)

  if request.method == 'POST':
    product.Name = request.form['Name']
    product.Price = float(request.form['Price'])
    product.Quantity_Available = int(request.form['Quantity Available'])
    product.Category_ID = int(request.form['Category'])
    product.Unit = request.form['Unit']
    database.session.commit()
    flash('Product updated successfully.', 'success')
    return redirect(url_for('admin_home'))

  categories = Category.query.all()
  return render_template('update_existing_product.html',
                         product=product,
                         categories=categories)


# Delete Product Route
@app.route('/delete_existing_product/<int:product_id>',
           methods=['GET', 'POST'])
#@login_required
def delete_existing_product(product_id):
  product = Products.query.get_or_404(product_id)

  if request.method == 'POST':
    #confirm = request.form.get('confirm')
    #if confirm == 'Yes':
    database.session.delete(product)
    database.session.commit()
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('admin_home'))
  #else:
  #   flash('Product deletion canceled.', 'warning')
  #  return redirect(url_for('admin_home'))

  return render_template('delete_existing_product.html', product=product)


@app.route('/summary', methods=['GET','POST'])
def summary():
  # Retrieve data from the cart_history table
  cart_history = CartHistory.query.all()
  products = Products.query.all()

  # Convert cart history data to a DataFrame for easy manipulation
  df_cart_history = pd.DataFrame(
    [(item.product_name, item.quantity, item.order_date)
     for item in cart_history],
    columns=['Product Name', 'Quantity', 'Order Date'])

  # Create a dictionary to map product names to prices
  price_dict = {product.Name: product.Price for product in products}

  # Add the 'Price' column to the DataFrame by mapping the prices based on the product names
  df_cart_history['Price'] = df_cart_history['Product Name'].map(price_dict)

  fig1 = px.bar(df_cart_history,
                x='Product Name',
                y='Quantity',
                title='Total Quantity Sold per Product')
  fig1.update_layout(
    xaxis=dict(range=[0, None]))  # Adjust the x-axis minimum limit
  fig1.update_layout(
    yaxis=dict(range=[0, None]))  # Adjust the y-axis minimum limit

  fig2 = px.line(df_cart_history,
                 x='Order Date',
                 y='Quantity',
                 title='Quantity Sold Over Time')
  fig2.update_layout(
    xaxis=dict(range=[0, None]))  # Adjust the x-axis minimum limit
  fig2.update_layout(
    yaxis=dict(range=[0, None]))  # Adjust the y-axis minimum limit

  fig3, ax3 = plt.subplots()
  top_product_by_quantity = df_cart_history.groupby(
    'Product Name', as_index=False)['Quantity'].sum()
  fig3 = px.bar(top_product_by_quantity,
                x='Product Name',
                y='Quantity',
                title='Products with Highest Quantity Sold')
  fig3.update_layout(
    xaxis=dict(range=[0, None]))  # Adjust the x-axis minimum limit
  fig3.update_layout(
    yaxis=dict(range=[0, None]))  # Adjust the y-axis minimum limit

  # Graph 4: Products Generating Maximum Revenue
  list_revenue = []
  for i in range(len(df_cart_history)):
    list_revenue.append(
      float(df_cart_history['Quantity'][i]) *
      float(df_cart_history['Price'][i]))
  df_cart_history['Revenue'] = list_revenue
  top_products_by_revenue = df_cart_history.groupby(
    'Product Name', as_index=False)['Revenue'].sum()
  fig4 = px.bar(top_products_by_revenue,
                x='Product Name',
                y='Revenue',
                title='Products Generating Maximum Revenue')

  fig4.update_layout(
    xaxis=dict(range=[0, None]))  # Adjust the x-axis minimum limit
  fig4.update_layout(
    yaxis=dict(range=[0, None]))  # Adjust the y-axis minimum limit

  graph1_html = fig1.to_html(full_html=False)
  graph2_html = fig2.to_html(full_html=False)
  graph3_html = fig3.to_html(full_html=False)
  graph4_html = fig4.to_html(full_html=False)

  return render_template('summary.html',
                         graph1_html=graph1_html,
                         graph2_html=graph2_html,
                         graph3_html=graph3_html,
                         graph4_html=graph4_html)


#Note : 'POST' Method is used by user to send or post some information to the Server or Some Source,
#while 'GET' can used to get/request some information/data for the user from Some Source like the Server without modifying any server side resourse.
@app.route('/', methods=['GET', 'POST'])
def user_signup():
  try:
    if request.method == 'POST':
      username = request.form['username']
      email = request.form['email']
      password = request.form['password']
      usertype = request.form['usertype']
      #gender = request.form['gender']

      if not all([username, email, password,usertype
                  ]):  #Checking if all fields are entered.
        flash('All fields are required.', 'error')
        return redirect(
          url_for('user_signup')
        )  #Redirecting to the same page,if the user has not entered all the fields.

      existing_user = Users.query.filter_by(Username=username).first()
      if existing_user:  #If the user already exists,we display the following error.
        flash('Username already exists,Please choose a different username.',
              'error')
        return redirect(url_for('user_signup'))

      existing_email_id = Users.query.filter_by(Email_ID=email).first()
      if existing_email_id:  #If the email already exists,we display the following error.
        flash('Email-ID already taken,Please choose a email_id.', 'error')
        return redirect(url_for('user_signup'))

      #We hash the User's apssword for security purposes.
      hashed_password = generate_password_hash(password)
      #We add the new user to the Users Table.
      new_user = Users(Username=username,
                       Email_ID=email,
                       Hashed_Password=hashed_password,
                       Usertype=usertype)
      database.session.add(new_user)
      database.session.commit()
      flash('Registration successful. Please log in.', 'success')
      return redirect(url_for('user_login'))

  except Exception as e:
    flash(f"An error occurred during signup: {str(e)}", 'error')
    return redirect(url_for('user_signup'))

  return render_template('user_signup.html')


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
  if request.method == 'POST':
    username = request.form['username']
    password = request.form['password']
    usertype = request.form['usertype']

    user = Users.query.filter_by(Username=username).first()
    if user and user.check_password_existence(password):
      if usertype == 'customer' and user.Usertype == 'customer':
        login_user(user)
        return redirect(url_for('products_home'))
      elif usertype == 'admin' and user.Usertype == 'admin':
        login_user(user)
        return redirect(url_for('admin_home'))
      else:
        flash('Invalid user type for this user.', 'error')
        return redirect(url_for('user_login'))
    else:
      flash('Invalid username or password.', 'error')
      return redirect(url_for('user_login'))

  return render_template('user_login.html')


#when login_required is invoked Flask-Login extension will redirect the user to the login page, where they can log in to gain access to the webpage/webapp.
#This Clears all the session data.
@app.route('/user_logout')
#@login_required
def user_logout():
  logout_user(
  )  #This logs the user out of the webpage and terminates the session.
  flash('You have been logged out.', 'info')
  return redirect(url_for('user_login'))


@app.before_request
def before_request():
  if request.method == "OPTIONS":
    # Handle CORS preflight request
    headers = {
      "Access-Control-Allow-Origin": "*",  # Allow requests from any origin
      "Access-Control-Allow-Methods":
      "POST, GET, OPTIONS",  # Allow POST, GET, and OPTIONS methods
      "Access-Control-Allow-Headers":
      "Content-Type, Authorization",  # Allow specific headers
    }
    response = make_response(jsonify({}), 200, headers)
  else:
    # For other requests, add CORS headers to allow requests from any origin
    response = None

  if response:
    response.headers["Access-Control-Allow-Origin"] = "*"

  return response


if __name__ == '__main__':
  with app.app_context():
    database.create_all()
    # Run the Flask app on the specified port
    app.run(host='0.0.0.0', port=port, debug=True)
