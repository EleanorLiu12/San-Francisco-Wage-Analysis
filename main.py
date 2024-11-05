from flask import Flask, jsonify, request, make_response, render_template_string, Response
import pandas as pd
import time
import re
import matplotlib.pyplot as plt
import numpy as np
import io
import matplotlib



# Ensure the Agg backend is used
matplotlib.use('Agg')

app = Flask(__name__)

# Load the CSV data into a DataFrame
data = pd.read_csv('main.csv')

# Dictionary to track the last access time of IP addresses for rate limiting
rate_limit = {}
# List to store IPs that have visited the browse.json resource
visitor_ips = []

# Global variables for A/B testing
visit_count = 0
donation_count_a = 0
donation_count_b = 0

# Global variable to track the number of subscribed users
num_subscribed = 0


@app.route('/')
def index():
    global visit_count

    # Increment visit count
    visit_count += 1

    # Determine which version to show (A or B)
    if visit_count <= 10:
        version = 'A' if visit_count % 2 == 1 else 'B'
    else:
        version = 'A' if donation_count_a > donation_count_b else 'B'

    # Create the donation link based on the version
    if version == 'A': 
        donate_link = '<a href="/donate.html?from=A" style="color: blue;">Donate</a>'
    else:
        donate_link = '<a href="/donate.html?from=B" style="color: red;">Donate</a>'



    return f'''
        <html>
            <head>
                <title>Index</title>
                <script src="https://code.jquery.com/jquery-3.4.1.js"></script>
                <script>
                    function subscribe() {{
                        var email = prompt("What is your email?", "????");

                        $.post({{
                            type: "POST",
                            url: "/email",
                            data: email,
                            contentType: "application/text; charset=utf-8",
                            dataType: "json"
                        }}).done(function(data) {{
                            alert(data);
                        }}).fail(function(data) {{
                            alert("POST failed");
                        }});
                    }}
                </script>
            </head>
            
            <body>
                <h1>Index</h1>
                <ul>
                    <li><a href="/browse.html">Browse</a></li>
                    <li><a href="/browse.json">Browse JSON</a></li>
                    <li>{donate_link}</li>
                </ul>
                <form action="/send_email" method="post">
                    <label for="email">Enter your email to receive updates:</label><br>
                    <input type="email" id="email" name="email" required><br><br>
                    <input type="submit" value="Send Email">
                </form>              
                <button onclick="subscribe()">Subscribe</button>              
            </body>
            
            <body>
                <h2>Dashboard</h2>
                <img src="/dashboard1.svg"><br><br>
                <img src="/dashboard1-query.svg"><br><br>
                <img src="/dashboard2.svg"><br><br>
            </body>
        </html>
    '''





@app.route('/browse.html')
def browse():
    # Drop columns that only contain NaN values
    cleaned_data = data.dropna(axis=1, how='all')
    
    # Convert cleaned DataFrame to HTML table with custom styles
    table_html = cleaned_data.to_html(index=False, border=1, classes='data-table')

    # Add custom CSS for styling
    html_content = f'''
    <html>
        <head>
            <title>Browse</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f9f9f9;
                    margin: 0;
                    padding: 20px;
                    text-align: center;
                }}
                h1 {{
                    font-size: 2em;
                    margin-bottom: 20px;
                }}
                .data-table {{
                    margin: 0 auto;
                    border-collapse: collapse;
                    width: 95%;
                }}
                .data-table th, .data-table td {{
                    border: 1px solid #ccc;
                    padding: 8px;
                    text-align: center;
                }}
                .data-table th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <h1>Browse</h1>
            {table_html}
        </body>
    </html>
    '''
    
    return html_content

@app.route('/browse.json')
def browse_json():
    client_ip = request.remote_addr
    current_time = time.time()
    
    # Check if the client IP is allowed to access the data
    if client_ip in rate_limit and (current_time - rate_limit[client_ip] < 60):
        retry_after = 60 - (current_time - rate_limit[client_ip])
        response = make_response(
            jsonify({"error": "Rate limit exceeded. Try again later."}), 429
        )
        response.headers['Retry-After'] = str(int(retry_after))
        return response
    
    # Update the last access time for the client IP
    rate_limit[client_ip] = current_time
    
    # Add client IP to visitor list if it's not already there
    if client_ip not in visitor_ips:
        visitor_ips.append(client_ip)
    
    # Drop columns that only contain NaN values
    cleaned_data = data.dropna(axis=1, how='all')
    
    # Convert the cleaned DataFrame to a JSON format
    json_data = cleaned_data.to_dict(orient='records')
    return jsonify(json_data)

@app.route('/visitors.json')
def visitors():
    # Return the list of IP addresses that have visited browse.json
    return jsonify({"visitors": visitor_ips})

@app.route('/donate.html')
def donate():
    global donation_count_a, donation_count_b

    # Check if there's a query string for version tracking
    version = request.args.get('from', default=None)

    # Increment the donation count for the corresponding version
    if version == 'A':
        donation_count_a += 1
    elif version == 'B':
        donation_count_b += 1

    return '''
        <html>
            <head>
                <title>Donate</title>
            </head>
            <body>
                <h1>Donate</h1>
                <p>Your support is crucial to help us keep this project running. By donating, you contribute to
                the development and maintenance of our data platform, enabling us to provide free and open access 
                to quality information. Every donation, big or small, makes a difference!</p>
                <p>Thank you for considering a donation to our project. Together, we can keep our data open and 
                accessible for everyone.</p>
            </body>
        </html>
    '''



@app.route('/email', methods=["POST"])
def email():
    global num_subscribed
    email = str(request.data, "utf-8").strip()
    
    # Regex pattern for validating an email address
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{3}$'
    
    # Check if the email matches the pattern
    if re.match(email_pattern, email):
        with open("emails.txt", "a") as f:  # open file in append mode
            f.write(email + "\n")  # Write valid email on a new line
        num_subscribed += 1  # Increment the subscription count
        return jsonify(f"Thanks, your subscriber number is {num_subscribed}!")
    
    return jsonify("Please stop being so careless and enter a valid email address!")
       
    
 








@app.route('/dashboard1.svg')
def histogram_total_compensation():
    fig, ax = plt.subplots()
    data['Total Compensation'] = data['Total Compensation'].replace({'\$': '', ',': ''}, regex=True).astype(float)
    
    # Histogram for Total Compensation
    ax.hist(data['Total Compensation'].dropna(), bins=30, color='skyblue', edgecolor='black')
    ax.set_xlabel('Total Compensation')
    ax.set_ylabel('Frequency')
    ax.set_title('Distribution of Total Compensation')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='svg')
    buf.seek(0)
    plt.close(fig)
    
    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'image/svg+xml'
    return response
    
    # return Response(buf.getvalue(), mimetype='image/svg+xml')

@app.route('/dashboard1-query.svg')
def barplot_base_salary_by_specialism():
    # Create a new figure and axes
    fig, ax = plt.subplots()
    
    # Clean and prepare the data
    data['Base'] = data['Base'].replace({'\$': '', ',': ''}, regex=True).astype(float)

    # Calculate mean Base salary by Specialism
    base_by_specialism = data.groupby('Specialism')['Base'].mean().dropna().sort_values()

    # Create the bar plot
    base_by_specialism.plot(kind='bar', color='skyblue', ax=ax)
    ax.set_ylabel('Average Base Salary ($)')
    ax.set_title('Average Base Salary by Specialism')
    ax.set_xlabel('Specialism')
    plt.xticks(rotation=45, ha='right')

    # Save the figure to a BytesIO buffer
    plt.savefig('dashboard1-query.svg')
    buf = io.BytesIO()
    plt.savefig(buf, format='svg')
    buf.seek(0)
    plt.close(fig)
    print("picture")

    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'image/svg+xml'
    return response
    # return Response(buf.getvalue(), mimetype='image/svg+xml')

@app.route('/dashboard2.svg')
def barplot_bonus_by_specialism():
    fig, ax = plt.subplots()
    data['Bonus'] = data['Bonus'].replace({'\$': '', ',': ''}, regex=True).astype(float)
    
    # Calculate mean Bonus by Specialism
    bonus_by_specialism = data.groupby('Specialism')['Bonus'].mean().dropna().sort_values()
    
    # Bar plot for average Bonus by Specialism
    bonus_by_specialism.plot(kind='bar', color='salmon', ax=ax)
    ax.set_ylabel('Average Bonus')
    ax.set_title('Average Bonus by Specialism')
    ax.set_xlabel('Specialism')
    plt.xticks(rotation=45, ha='right')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='svg')
    buf.seek(0)
    plt.close(fig)
    
    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'image/svg+xml'
    return response
    # return Response(buf.getvalue(), mimetype='image/svg+xml')
    




if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, threaded=False)  # don't change this line!
