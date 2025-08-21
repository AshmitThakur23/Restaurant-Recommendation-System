# app.py
import os
import pandas as pd
from flask import Flask, render_template, request, send_from_directory
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

DATASET_PATH = 'zomato.csv' 

CUISINE_COLUMN = 'cuisines'
LOCATION_COLUMN = 'locality' 
RATING_COLUMN = 'aggregate_rating'
NAME_COLUMN = 'name'
ADDRESS_COLUMN = 'address'
VOTES_COLUMN = 'votes'
zomato_data = None
DATA_LOAD_ERROR = None 

try:
    logging.info(f"Attempting to load dataset from {DATASET_PATH}...")
  
    try:
        zomato_data = pd.read_csv(DATASET_PATH, encoding='utf-8')
    except UnicodeDecodeError:
        logging.warning("UTF-8 decoding failed, trying 'latin1' encoding for zomato.csv.")
        try:
            zomato_data = pd.read_csv(DATASET_PATH, encoding='latin1')
        except UnicodeDecodeError:
            logging.warning("latin1 decoding also failed, trying 'ISO-8859-1' for zomato.csv.")
            zomato_data = pd.read_csv(DATASET_PATH, encoding='ISO-8859-1') # Common fallback

    logging.info(f"Dataset '{DATASET_PATH}' loaded successfully.")
    logging.info(f"Raw columns from CSV: {zomato_data.columns.tolist()}")
    original_columns = zomato_data.columns.tolist()
    zomato_data.columns = [col.strip().lower().replace(' ', '_') for col in original_columns]
    logging.info(f"Standardized column names: {zomato_data.columns.tolist()}")
    logging.info(f"Number of rows loaded: {len(zomato_data)}")



    required_columns = [
        NAME_COLUMN, CUISINE_COLUMN, LOCATION_COLUMN, RATING_COLUMN,
        ADDRESS_COLUMN, VOTES_COLUMN
    ]

    if not all(col in zomato_data.columns for col in required_columns):
        missing = [col for col in required_columns if col not in zomato_data.columns]
        DATA_LOAD_ERROR = (f"Missing one or more required columns in CSV after standardization: {missing}. "
                           f"Please ensure your `app.py` column constants ({', '.join(required_columns)}) "
                           f"match the standardized headers from your '{DATASET_PATH}' file (all lowercase, spaces replaced by underscores). "
                           f"Available columns: {zomato_data.columns.tolist()}")
        logging.error(DATA_LOAD_ERROR)
        zomato_data = pd.DataFrame() 
    else:
        logging.info(f"All required columns ({', '.join(required_columns)}) are present in the standardized dataset.")

        zomato_data[RATING_COLUMN] = pd.to_numeric(zomato_data[RATING_COLUMN], errors='coerce').fillna(0)
        zomato_data[VOTES_COLUMN] = pd.to_numeric(zomato_data[VOTES_COLUMN], errors='coerce').fillna(0)
        zomato_data[NAME_COLUMN] = zomato_data[NAME_COLUMN].astype(str).fillna('Name N/A')
        zomato_data[CUISINE_COLUMN] = zomato_data[CUISINE_COLUMN].astype(str).fillna('Cuisine N/A')
        zomato_data[LOCATION_COLUMN] = zomato_data[LOCATION_COLUMN].astype(str).fillna('Location N/A')
        zomato_data[ADDRESS_COLUMN] = zomato_data[ADDRESS_COLUMN].astype(str).fillna('Address N/A')
        logging.info("Relevant columns converted and cleaned.")

except FileNotFoundError:
    DATA_LOAD_ERROR = (f"Error: Dataset file not found at {DATASET_PATH}. "
                       f"Ensure '{DATASET_PATH}' is in the same directory as app.py.")
    logging.error(DATA_LOAD_ERROR)
    zomato_data = pd.DataFrame()
except pd.errors.EmptyDataError:
    DATA_LOAD_ERROR = f"Error: Dataset file '{DATASET_PATH}' is empty."
    logging.error(DATA_LOAD_ERROR)
    zomato_data = pd.DataFrame()
except Exception as e:
    DATA_LOAD_ERROR = f"An unexpected error occurred during dataset loading or processing: {e}"
    logging.error(DATA_LOAD_ERROR, exc_info=True) # Log full traceback
    zomato_data = pd.DataFrame()


@app.route('/')
def index():


    initial_error = DATA_LOAD_ERROR if zomato_data is None or zomato_data.empty else None

    return render_template('index.html', results=None, error=initial_error,
                           previous_cuisine_query='', # Pass variable named previous_cuisine_query
                           previous_location_query='', # Pass variable named previous_location_query
                           NAME_COLUMN=NAME_COLUMN,
                           ADDRESS_COLUMN=ADDRESS_COLUMN,
                           CUISINE_COLUMN=CUISINE_COLUMN,
                           LOCATION_COLUMN=LOCATION_COLUMN,
                           RATING_COLUMN=RATING_COLUMN,
                           VOTES_COLUMN=VOTES_COLUMN)


@app.route('/find-restaurants', methods=['GET'])
def find_restaurants():
   
    logging.info(f"--- Inside /find-restaurants ---")
    logging.info(f"Received request.args: {request.args}") # Logs all query parameters received

    cuisine_query = request.args.get('cuisine_query', '').strip().lower()
    location_query = request.args.get('location_query', '').strip().lower()
    logging.info(f"Parsed cuisine_query: '{cuisine_query}', location_query: '{location_query}'")

    
    if zomato_data is None or zomato_data.empty:
        error_message = DATA_LOAD_ERROR or "Restaurant data is not available. Please check server logs."
        logging.error(f"Data not available for search. Error: {error_message}")
        return render_template('index.html', results=[], error=error_message,
                               previous_cuisine_query=cuisine_query, # Pass back entered query
                               previous_location_query=location_query, # Pass back entered query
                               # Pass standardized column names to the template
                               NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                               CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                               RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)

    if not cuisine_query and not location_query:
        error_message = "Please enter a cuisine (e.g., Italian, Pizza) and/or a location to search."
        logging.info("Search attempt with no query parameters.")
        return render_template('index.html', results=[], error=error_message,
                               previous_cuisine_query=cuisine_query,
                               previous_location_query=location_query,
                            
                               NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                               CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                               RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)

    try:
        filtered_data = zomato_data.copy()
        search_performed = False

        if cuisine_query:
            search_performed = True
            logging.info(f"Filtering by cuisine: '{cuisine_query}' using column '{CUISINE_COLUMN}'")
          
            if CUISINE_COLUMN in filtered_data.columns:

                filtered_data = filtered_data[
                    filtered_data[CUISINE_COLUMN].str.lower().str.contains(cuisine_query.lower(), na=False)
                ]
                logging.info(f"Rows after cuisine filter: {len(filtered_data)}")
            else:
                 logging.warning(f"Cuisine column '{CUISINE_COLUMN}' not found in dataset for filtering.")


        if location_query:
            search_performed = True
            logging.info(f"Filtering by location: '{location_query}' using column '{LOCATION_COLUMN}'")
            
            if LOCATION_COLUMN in filtered_data.columns:

                filtered_data = filtered_data[
                    filtered_data[LOCATION_COLUMN].str.lower().str.contains(location_query.lower(), na=False)
                ]
                logging.info(f"Rows after location filter: {len(filtered_data)}")
            else:
                logging.warning(f"Location column '{LOCATION_COLUMN}' not found in dataset for filtering.")

        if not search_performed and (cuisine_query or location_query):
             logging.warning("Search was requested but no valid filtering columns were available.")
             return render_template('index.html', results=[],
                                error="Cannot perform search: Required data columns are missing or invalid.",
                                previous_cuisine_query=cuisine_query,
                                previous_location_query=location_query,
                                NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                                CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                                RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)



        sort_by_columns = []
        ascending_order = []

        if RATING_COLUMN in filtered_data.columns:
            sort_by_columns.append(RATING_COLUMN)
            ascending_order.append(False) # Rating descending
       
        if VOTES_COLUMN in filtered_data.columns:
             sort_by_columns.append(VOTES_COLUMN)
             ascending_order.append(False) # Votes descending
        if NAME_COLUMN in filtered_data.columns:
            sort_by_columns.append(NAME_COLUMN)
            ascending_order.append(True) # Name ascending

        if sort_by_columns:
            logging.info(f"Sorting by {sort_by_columns} with ascending order {ascending_order}")

            try:
                sorted_restaurants_df = filtered_data.sort_values(by=sort_by_columns, ascending=ascending_order)
            except KeyError as e:
                 logging.error(f"Sorting failed because a column was missing: {e}", exc_info=True)
                 sorted_restaurants_df = filtered_data 
        else:
            logging.warning("No valid columns found for sorting (Rating, Votes, or Name). Results will be unsorted.")
            sorted_restaurants_df = filtered_data


        
        columns_to_display_possible = [NAME_COLUMN, ADDRESS_COLUMN, CUISINE_COLUMN, LOCATION_COLUMN, RATING_COLUMN, VOTES_COLUMN]
        columns_to_display_actual = [col for col in columns_to_display_possible if col in sorted_restaurants_df.columns]

        if not columns_to_display_actual:

             error_message = "Cannot display results: Essential data columns are missing."
             logging.error(error_message + f" Missing columns: {list(set(columns_to_display_possible) - set(sorted_restaurants_df.columns))}")
             return render_template('index.html', results=[], error=error_message,
                                previous_cuisine_query=cuisine_query, previous_location_query=location_query,
                                NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                                CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                                RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)


        restaurants_list_of_dicts = sorted_restaurants_df[columns_to_display_actual].to_dict('records')

        if not restaurants_list_of_dicts:
            search_terms_log = []
            if cuisine_query: search_terms_log.append(f"cuisine '{cuisine_query}'")
            if location_query: search_terms_log.append(f"location '{location_query}'")
            log_msg = f"No restaurants found matching {(' and '.join(search_terms_log) if search_terms_log else 'your criteria')}."
            error_message_display = f"No restaurants found for the specified criteria. Try broadening your search."
            if not search_terms_log: 
                error_message_display = "Please enter a cuisine and/or location." # Redundant due to earlier check, but safe

            logging.info(log_msg)
            return render_template('index.html', results=[], error=error_message_display,
                                   previous_cuisine_query=cuisine_query, previous_location_query=location_query,
        
                                   NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                                   CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                                   RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)
        else:
            logging.info(f"Found {len(restaurants_list_of_dicts)} matching restaurants. Displaying results.")
            return render_template('index.html', results=restaurants_list_of_dicts, error=None,
                                   previous_cuisine_query=cuisine_query, previous_location_query=location_query,
                                   
                                   NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                                   CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                                   RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)

    except KeyError as e:

        error_message = f"Internal Error: A data column was not found ({e}). Check column names in app.py and your CSV."
        logging.error(f"{error_message} - Exception: {e}", exc_info=True)
        return render_template('index.html', results=[], error=error_message,
                               previous_cuisine_query=cuisine_query, previous_location_query=location_query,
                               NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                               CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                               RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)
    except Exception as e:
        error_message = "An unexpected error occurred while searching. Please check server logs."
        logging.error(f"An unexpected error occurred during data filtering: {e}", exc_info=True)
        return render_template('index.html', results=[], error=error_message,
                               previous_cuisine_query=cuisine_query, previous_location_query=location_query,
                               NAME_COLUMN=NAME_COLUMN, ADDRESS_COLUMN=ADDRESS_COLUMN,
                               CUISINE_COLUMN=CUISINE_COLUMN, LOCATION_COLUMN=LOCATION_COLUMN,
                               RATING_COLUMN=RATING_COLUMN, VOTES_COLUMN=VOTES_COLUMN)

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files like CSS and images."""

    return send_from_directory('static', filename)

if __name__ == '__main__':
    logging.info("Starting Flask application...")
    app.run(debug=True, host='0.0.0.0', port=5000)