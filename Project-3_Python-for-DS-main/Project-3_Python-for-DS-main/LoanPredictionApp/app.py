from flask import Flask, render_template, request, redirect, url_for, session, flash
import joblib
import mysql.connector
import secrets
import pickle
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

# Generate a secure secret key for session management
secure_key = secrets.token_hex(16)

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = secure_key  # Set the secret key for the Flask session

# Set up MySQL Database Configuration
db = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="root",
    database="loan_approval"
)
cursor = db.cursor()

# Create the `users` table if it does not exist to store login credentials
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
)
""")
db.commit()

# Load the saved loan approval model and the columns used during training
model = joblib.load('loan_approval_model.pkl')
with open('columns.pkl', 'rb') as file:
    columns = pickle.load(file)

# Route to handle the browser's default request for a favicon
@app.route('/favicon.ico')
def favicon():
    return '', 204  # Return an empty response with a status code of 204 (No Content)

# Home route that displays the home page
@app.route('/')
def home():
    return render_template('home.html')

# Route to handle user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)  # Hash the password for security

        # Check if the username already exists in the database
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        # If the username exists, show a message; otherwise, add the new user
        if existing_user:
            return redirect(url_for('register', message="Username already exists. Please choose a different username."))
        
        # Insert the new user into the `users` table and commit to the database
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            db.commit()
            return redirect(url_for('register', message="User successfully added! Please click OK to confirm."))
        except mysql.connector.Error as err:
            return redirect(url_for('register', message=f"Error: {err}"))

    return render_template('register.html')

# Route to handle user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query the database to retrieve user details
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        # Check if the password matches the stored hash and start the session
        if user and check_password_hash(user[2], password):
            session['username'] = username
            flash("Login successful!")
            return redirect(url_for('predict'))  # Redirect to the prediction page after login
        else:
            return redirect(url_for('login', message="Invalid username or password. Please try again."))

    return render_template('login.html')

# Enter Details API to render the form
@app.route('/enter_details', methods=['GET'])
def enter_details():
    if 'username' not in session:
        flash("You need to log in first.")
        return redirect(url_for('login'))
    
    return render_template('predict.html', username=session['username'])

# Predict API to handle the form submission and make predictions
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    # Check if user is logged in
    if 'username' not in session:
        flash("You need to log in first.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Read the values from the form
            gender = request.form['gender']
            married = request.form['married']
            dependents = request.form['dependents']
            education = request.form['education']
            self_employed = request.form['self_employed']
            applicant_income = int(request.form['applicant_income'])
            coapplicant_income = float(request.form['coapplicant_income'])
            loan_amount = float(request.form['loan_amount'])
            loan_amount_term = float(request.form['loan_amount_term'])
            credit_history = int(request.form['credit_history'])
            property_area = request.form['property_area']

            # Create a feature dictionary using the extracted values
            feature_dict = {
                'gender': [gender],
                'married': [married],
                'dependents': [dependents],
                'education': [education],
                'self_employed': [self_employed],
                'applicantincome': [applicant_income],
                'coapplicantincome': [coapplicant_income],
                'loanamount': [loan_amount],
                'loan_amount_term': [loan_amount_term],
                'credit_history': [credit_history],
                'property_area': [property_area]
            }

            # Create a DataFrame using the feature dictionary
            feature_df = pd.DataFrame(feature_dict)

            # Encode categorical variables based on training mappings
            encoding_mappings = {
                'gender': {'male': 1, 'female': 0},
                'married': {'yes': 1, 'no': 0},
                'dependents': {'0': 0, '1': 1, '2': 2, '3+': 3},
                'education': {'graduate': 1, 'not_graduate': 0},
                'self_employed': {'yes': 1, 'no': 0},
                'property_area': {'urban': 2, 'semiurban': 1, 'rural': 0}
            }

            # Map the categorical values to numbers as per the encoding during training
            for col, mapping in encoding_mappings.items():
                feature_df[col] = feature_df[col].map(mapping)

            # Ensure all columns match the expected input features
            feature_df_aligned = feature_df.reindex(columns=columns, fill_value=0)
            feature_df_aligned = feature_df_aligned.astype(float)

            # Pass the aligned DataFrame to the model for prediction
            prediction = model.predict(feature_df_aligned)

            # Format the prediction text with additional details
            if prediction[0] == 1:
                prediction_text = f"Congrats!! You are eligible for the loan of {loan_amount} (K $) for a Loan Term of {loan_amount_term} months."
            else:
                prediction_text = f"Sorry!! You are not eligible for the loan of {loan_amount} (K $) for a Loan Term of {loan_amount_term} months."

            # Render the result on the predict.html page
            return render_template('predict.html', prediction_text=prediction_text, username=session['username'])

        except KeyError as e:
            # Handle missing form fields
            flash(f"Missing form field: {e}")
            return render_template('predict.html', username=session['username']), 400

    # On GET request, simply render the form for the user to input details
    return render_template('predict.html', username=session['username'])

# Logout route to clear the session
@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove the username from the session
    flash("You have been logged out successfully.")
    return redirect(url_for('login'))

# Run the Flask Application
if __name__ == '__main__':
    app.run(debug=True)  # Start the Flask application in debug mode
