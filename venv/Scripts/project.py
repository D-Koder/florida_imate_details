import os
import sys
import requests
import threading
import logging
from bs4 import BeautifulSoup
from pymongo import MongoClient
import tkinter as tk
from tkinter import ttk, messagebox

# Setup logging
logging.basicConfig(
    filename='application.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# Dynamically import config.py from the same directory as the executable
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

sys.path.append(application_path)

# Load the config module
try:
    import config
    logging.info("Config module loaded successfully")
except ImportError as e:
    logging.error("Error: config.py not found")
    sys.exit(1)

# Use the connection details from the configuration file
serverName = config.serverName
dbName = config.dbName
collectionName = config.collectionName

def fetch_inmate_details(dc_number):
    """
    Fetch inmate details from the Florida Department of Corrections website using the provided DC number.

    Args:
        dc_number (str): The DC number of the inmate.

    Returns:
        dict: A dictionary containing the inmate's details if found, None otherwise.
    """
    url = f"https://pubapps.fdc.myflorida.com/offenderSearch/detail.aspx?Page=Detail&DCNumber={dc_number}&TypeSearch=AI"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    inmate_info = {}

    # Check if the page loaded correctly
    if "Inmate Population Information Detail" in soup.title.string:
        logging.info(f"Inmate details found with search type AI for DC Number: {dc_number}")

        # Extracting general information
        name_element = soup.find('th', string='Name:')
        if name_element:
            inmate_info = {
                'DC Number': dc_number,
                'Name': name_element.find_next_sibling('td').text.strip(),
                'Race': soup.find('th', string='Race:').find_next_sibling('td').text.strip(),
                'Sex': soup.find('th', string='Sex:').find_next_sibling('td').text.strip(),
                'Birth Date': soup.find('th', string='Birth Date:').find_next_sibling('td').text.strip(),
            }
            logging.info(inmate_info)
            # Check if essential fields are missing
            if not inmate_info['Name'] or not inmate_info['Race']:
                logging.warning(f"Essential details missing for DC Number: {dc_number}")
                return None

            # Extracting current prison sentence history
            sentence_history = []
            sentence_table = soup.find('div', {'id': 'ctl00_ContentPlaceHolder1_divCurrentPrison'}).find('table')
            for row in sentence_table.find_all('tr')[1:]:  # Skip header row
                columns = row.find_all('td')
                history = {
                    'Offense Date': columns[0].text.strip(),
                    'Offense': columns[1].text.strip(),
                    'Sentence Date': columns[2].text.strip(),
                    'County': columns[3].text.strip(),
                    'Case Number': columns[4].text.strip(),
                    'Prison Sentence Length': columns[5].text.strip(),  
                }
                sentence_history.append(history)

            inmate_info['Current Prison Sentence History'] = sentence_history

            # Extracting aliases
            aliases = soup.find('div', {'id': 'ctl00_ContentPlaceHolder1_divAlias'}).find('p').text.strip()
            inmate_info['Aliases'] = aliases

            # Extracting incarceration history
            incarceration_history = []
            incarceration_table = soup.find('div', {'id': 'ctl00_ContentPlaceHolder1_divIncarceration'}).find('table')
            for row in incarceration_table.find_all('tr')[1:]:  # Skip header row
                columns = row.find_all('td')
                history = {
                    'Date In-Custody': columns[0].text.strip(),
                    'Date Out-Custody': columns[1].text.strip(),
                }
                incarceration_history.append(history)

            inmate_info['Incarceration History'] = incarceration_history

        else:
            logging.error(f"Failed to retrieve inmate details with search type AI for DC Number: {dc_number}")
            return None

    return inmate_info

def store_inmate_details(inmate_info):
    """
    Store the inmate details in a MongoDB database.

    Args:
        inmate_info (dict): The inmate details to be stored.
    """
    logging.info(f"Storing inmate details to MongoDB for DC Number: {inmate_info['DC Number']}")
    try:
        # Connect to MongoDB server
        client = MongoClient(serverName)
        
        # Access the database
        db = client[dbName]
        
        # Access the collection
        collection = db[collectionName]
        
        # Insert or update inmate info
        collection.update_one(
            {'DC Number': inmate_info['DC Number']},
            {'$set': inmate_info},
            upsert=True
        )
        logging.info(f"Inmate details stored successfully for DC Number: {inmate_info['DC Number']}")
    except Exception as e:
        logging.error(f"Error storing inmate details: {e}")

def display_inmate_details(details):
    """
    Display the inmate details in the GUI.

    Args:
        details (dict): The inmate details to be displayed.
    """
    logging.info("Displaying inmate details in the GUI")
    # Clear previous details
    for widget in details_frame.winfo_children():
        widget.destroy()
    
    row = 0
    for key, value in details.items():
        if isinstance(value, list):
            continue  # Skip lists to handle them separately
        else:
            # Display general information
            ttk.Label(details_frame, text=f"{key}:").grid(column=0, row=row, sticky=tk.W, pady=2)
            ttk.Label(details_frame, text=value).grid(column=1, row=row, sticky=tk.W, pady=2)
            row += 1

    # Add Current Prison Sentence History table
    if 'Current Prison Sentence History' in details:
        ttk.Label(details_frame, text="Current Prison Sentence History:").grid(column=0, row=row, sticky=tk.W, pady=2)
        row += 1

        columns = ['Offense Date', 'Offense', 'Sentence Date', 'County', 'Case Number', 'Prison Sentence Length']
        tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=5)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, stretch=tk.NO)
        for item in details['Current Prison Sentence History']:
            tree.insert('', tk.END, values=[item[col] for col in columns])
        tree.grid(column=0, row=row, columnspan=2, pady=2, sticky="ew")

        row += 1
    
    # Add Incarceration History table
    if 'Incarceration History' in details:
        ttk.Label(details_frame, text="Incarceration History:").grid(column=0, row=row, sticky=tk.W, pady=2)
        row += 1

        columns = ['Date In-Custody', 'Date Out-Custody']
        tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=5)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, stretch=tk.NO)
        for item in details['Incarceration History']:
            tree.insert('', tk.END, values=[item[col] for col in columns])
        tree.grid(column=0, row=row, columnspan=2, pady=2, sticky="ew")

        row += 1

    # Configure column weights for proper alignment
    details_frame.grid_columnconfigure(0, weight=1)
    details_frame.grid_columnconfigure(1, weight=1)

def fetch_and_display_inmate_details():
    """
    Fetch inmate details from the website and display them in the GUI.
    """
    dc_number = dc_number_entry.get()
    if dc_number:
        threading.Thread(target=fetch_and_store_inmate_details, args=(dc_number,)).start()
    else:
        messagebox.showwarning("Input Error", "Please enter a DC number.")

def fetch_and_store_inmate_details(dc_number):
    """
    Fetch inmate details from the website, store them in the database, and update the GUI.
    """
    try:
        inmate_details = fetch_inmate_details(dc_number)
        if inmate_details:
            store_inmate_details(inmate_details)
            # Use after() to update the GUI from the main thread
            root.after(0, display_inmate_details, inmate_details)
        else:
            root.after(0, lambda: messagebox.showerror("Error", "Failed to retrieve valid inmate details."))
    except Exception as e:
        logging.error(f"Error fetching or storing inmate details: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))

# Create the main window
root = tk.Tk()
root.title("Prisoner Information Application")
root.state('zoomed')  # Make the window full screen

# Create and place widgets
ttk.Label(root, text="Enter DC Number:").grid(column=0, row=0, padx=10, pady=10)
dc_number_entry = ttk.Entry(root, width=20)
dc_number_entry.insert(0, "123456")  # Placeholder for the DC number
dc_number_entry.grid(column=1, row=0, padx=10, pady=10)
fetch_button = ttk.Button(root, text="Fetch Details", command=fetch_and_display_inmate_details)
fetch_button.grid(column=2, row=0, padx=10, pady=10)

# Frame for displaying inmate details
details_frame = ttk.Frame(root)
details_frame.grid(column=0, row=1, columnspan=3, padx=10, pady=10, sticky="ew")

# Run the GUI event loop
root.mainloop()
