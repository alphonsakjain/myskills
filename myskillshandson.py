from flask import Flask, render_template, request, redirect, url_for
import pyodbc
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from werkzeug.utils import secure_filename
import datetime
import redis
from decimal import Decimal  # Import the Decimal class

app = Flask(__name__)
cache_clear=False
# Azure SQL Database Configuration
server = 'mysqlserverhandson.database.windows.net'
database = 'myproductDB'
username = 'azureuser'
password = 'Bible@123'
driver= '{ODBC Driver 17 for SQL Server}'

# Azure Blob Storage Configuration
connection_string = 'DefaultEndpointsProtocol=https;AccountName=myproductcars;AccountKey=e/FvI00pR2FAZTAc7vsmb2s0nOcrqvy7Q47xwNLqvLfIz/qQR40tDfinOYhRddEXY0s4BlpH6yaQ+AStYazqnQ==;EndpointSuffix=core.windows.net'
container_name = 'myproductcarscontainer'
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

#Azure redis cache configuration
redis_password = 'wNA8T0eHzKHIYw1gbtUSWFZklniXH980oAzCaCXJd8k='
r = redis.StrictRedis(host='AutomobileWebsite.redis.cache.windows.net', port=6379, password=redis_password, db=0, decode_responses=True)

# Initialize database connection
def initialize_database():
    conn = pyodbc.connect('DRIVER=' + driver + ';SERVER=' + server + ';DATABASE=' + database + ';UID=' + username + ';PWD=' + password)
    cursor = conn.cursor()
    return conn, cursor

# Function to upload a file to Azure Blob Storage
def upload_to_azure_blob(file):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")  # Generate a timestamp
    filename = f"{timestamp}_{secure_filename(file.filename)}"  # Include timestamp in the blob name
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(file.read(), overwrite=True)  # Upload the file data

# Function to retrieve data from Azure SQL Database
def retrieve_data_from_sql():
    if cache_clear:
        r.flushall()
    #Check if data is cached
    cached_data = r.get('sql_data')
    if cached_data:
        cached_data = eval(cached_data, {"Decimal": Decimal})
        return cached_data
    conn, cursor = initialize_database()
    cursor.execute("SELECT Productid, ProductName, Price FROM Product")
    data = cursor.fetchall()
    conn.close()
    #Cache the data for future use
    r.set('sql_data', str(data), ex=3600)  # Cache for 1 hour (adjust as needed)
    return data

# Function to retrieve data from Azure Blob Storage
def retrieve_data_from_blob_storage():
    blobs = []
    for blob in container_client.list_blobs():
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob.name}"
        blobs.append(blob_url)
    return blobs

# Your Flask route for displaying products
@app.route('/display_products')
def display_products():
    sql_data = retrieve_data_from_sql()
    blob_data = retrieve_data_from_blob_storage()
    final_data = list(zip(sql_data, blob_data))
    redirect(url_for('display_products'))
    return render_template('display_products.html', final_data=final_data)

# Your Flask route for adding a product
@app.route('/add_product', methods=['GET','POST'])
def add_product():
    global cache_clear
    cache_clear=False
    if request.method == 'POST':
        product_name = request.form['product_name']
        price = request.form['price']
        photo = request.files['photo']

        if photo:
            upload_to_azure_blob(photo)  # Upload the photo to Azure Blob Storage

            #Initialize the database connection
            conn, cursor = initialize_database()
            # Insert product_name and price into the Products table
            cursor.execute("INSERT INTO Product (ProductName, Price) VALUES (?, ?)", (product_name, price))
            cache_clear=True
            # Commit the transaction and close the connection
            conn.commit()
            conn.close()
    return render_template('add_product.html')

if __name__ == '__main__':
    app.run()
