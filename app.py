import dash
from dash import dcc, html, Input, Output, State, dash_table, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import json
import io
import numpy as np
import sys

def get_season(month):
    if 3 <= month <= 5:
        return 'Spring'
    elif 6 <= month <= 8:
        return 'Summer'
    elif 9 <= month <= 11:
        return 'Autumn'
    else: # 12, 1, 2
        return 'Winter'
    
# --- Data Loading Function ---
def load_data():
    """
    Loads and processes all necessary CSV data for the dashboard.
    Assumes CSVs are in a 'data/' subdirectory relative to app.py.
    Returns a dictionary where each DataFrame is converted to a JSON string.
    """
    data = {}
    base_dir = os.path.dirname(__file__) # Gets the directory 
    data_dir = os.path.join(base_dir, 'data')

    try:
        products_path = os.path.join(data_dir, 'products_and_suppliers_combined.csv')
        df_products = pd.read_csv(products_path)
        df_products = df_products.rename(columns={'SupplierName': 'Supplier'}) 
        df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')

        if 'Weight' not in df_products.columns:
            df_products['Weight'] = 0.5 # Default weight of 0.5 kg per product entry for waste calculation

        data['products'] = df_products.to_json(date_format='iso', orient='split')
        
        
        purchases_path = os.path.join(data_dir, 'purchase_history.csv')
        df_purchases = pd.read_csv(purchases_path)
        df_purchases['PurchaseDate'] = pd.to_datetime(df_purchases['PurchaseDate'], errors='coerce')
        data['purchases'] = df_purchases.to_json(date_format='iso', orient='split')
        

        sales_path = os.path.join(data_dir, 'sales_data.csv')
        df_sales = pd.read_csv(sales_path)
        df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'])
        data['sales'] = df_sales.to_json(date_format='iso', orient='split')
        
         # Ensure SaleDate is datetime type and handle errors
        df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
        df_sales.dropna(subset=['SaleDate'], inplace=True)
        df_sales['Month'] = df_sales['SaleDate'].dt.month
        df_sales['Season'] = df_sales['Month'].apply(get_season)
        df_sales['Year'] = df_sales['SaleDate'].dt.year

        # Ensure TotalPrice is numeric and handle errors
        df_sales['TotalPrice'] = pd.to_numeric(df_sales['TotalPrice'], errors='coerce')
        df_sales.dropna(subset=['TotalPrice'], inplace=True)

        # Verify 'Profit' column exists and add fallback if not (as it should be there after running script)
        if 'Profit' not in df_sales.columns:
            print("CRITICAL WARNING: 'Profit' column not found in sales_data.csv. Please ensure you ran the 'add_profit_column.py' script successfully.")
            # Fallback (add random profit if missing, but ideally, fix the CSV)
            df_sales['Profit'] = df_sales['TotalPrice'] * np.random.uniform(0.15, 0.25, len(df_sales))

        

        inventory_path = os.path.join(data_dir, 'inventory_movements.csv')
        df_inventory = pd.read_csv(inventory_path)
        df_inventory['MovementDate'] = pd.to_datetime(df_inventory['MovementDate'])
        data['inventory'] = df_inventory.to_json(date_format='iso', orient='split')

        locations_path = os.path.join(data_dir, 'locations.csv')
        df_locations = pd.read_csv(locations_path)
        data['locations'] = df_locations.to_json(date_format='iso', orient='split')

        holidays_path = os.path.join(data_dir, 'holidays.csv')
        df_holidays = pd.read_csv(holidays_path)
        df_holidays['HolidayDate'] = pd.to_datetime(df_holidays['HolidayDate'])
        data['holidays'] = df_holidays.to_json(date_format='iso', orient='split')

        promotions_path = os.path.join(data_dir, 'promotions.csv')
        df_promotions = pd.read_csv(promotions_path)
        df_promotions['PromotionStartDate'] = pd.to_datetime(df_promotions['PromotionStartDate'])
        df_promotions['PromotionEndDate'] = pd.to_datetime(df_promotions['PromotionEndDate'])
        data['promotions'] = df_promotions.to_json(date_format='iso', orient='split')

        weather_path = os.path.join(data_dir, 'weather_data.csv')
        df_weather = pd.read_csv(weather_path)
        df_weather['WeatherDate'] = pd.to_datetime(df_weather['WeatherDate'])
        data['weather'] = df_weather.to_json(date_format='iso', orient='split')

        print("All data loaded successfully.")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}. Make sure the 'data' directory and CSV files exist.")
        data = {
            'products': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'sales': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'inventory': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'locations': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'holidays': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'promotions': pd.DataFrame().to_json(date_format='iso', orient='split'),
            'weather': pd.DataFrame().to_json(date_format='iso', orient='split')
        }
    return data

# Initialize app with Bootstrap themes
app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css',
    '/assets/custom.css'
],
                suppress_callback_exceptions=True 
)

server = app.server

# Initial data load
app_data = load_data()

# --- Helper Functions for Data Calculations ---
def get_realtime_metrics(stored_data_json):
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()
    df_inventory = pd.read_json(io.StringIO(stored_data_json['inventory']), orient='split') if stored_data_json.get('inventory') else pd.DataFrame()

    if not df_products.empty and 'ExpiryDate' in df_products.columns:
        df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')

    if not df_inventory.empty and 'MovementDate' in df_inventory.columns:
        df_inventory['MovementDate'] = pd.to_datetime(df_inventory['MovementDate'])

    if not df_inventory.empty:
        stock_in = df_inventory[df_inventory['MovementType'] == 'IN']['Quantity'].sum()
        stock_out = df_inventory[df_inventory['MovementType'] == 'OUT']['Quantity'].sum()
        items_in_stock = stock_in - stock_out
    else:
        items_in_stock = 0

    prev_items_in_stock = 12900 # Example dummy value
    stock_change_percent = ((items_in_stock - prev_items_in_stock) / prev_items_in_stock) * 100 if prev_items_in_stock else 0

    reorder_recommendations = 15 # Example dummy value
    prev_reorder_recommendations = 7 # Example dummy value
    reorder_change_percent = ((reorder_recommendations - prev_reorder_recommendations) / prev_reorder_recommendations) * 100 if prev_reorder_recommendations else 0

    if not df_products.empty:
        today = pd.to_datetime(datetime.now().date())
        expiring_items_count = df_products[
            (df_products['ExpiryDate'].notna()) &
            (df_products['ExpiryDate'] >= today) &
            (df_products['ExpiryDate'] <= today + timedelta(days=30))
        ].shape[0]
    else:
        expiring_items_count = 0

    prev_expiring_items = 8.4 # Example dummy value
    expiring_change_percent = ((expiring_items_count - prev_expiring_items) / prev_expiring_items) * 100 if prev_expiring_items else 0

    return {
        'items_in_stock': f"{items_in_stock:,.0f}",
        'stock_change': f"{stock_change_percent:+.0f}%", # Added + for positive change
        'stock_change_class': 'positive' if stock_change_percent >= 0 else 'negative',
        'reorder_recommendations': f"{reorder_recommendations}",
        'reorder_change': f"{reorder_change_percent:+.0f}%",
        'reorder_change_class': 'positive' if reorder_change_percent >= 0 else 'negative',
        'expiring_items': f"{expiring_items_count}",
        'expiring_change': f"{expiring_change_percent:+.0f}%",
        'expiring_change_class': 'negative' if expiring_change_percent >= 0 else 'positive', # Negative for expiring is 'bad'
    }

def get_sales_data_for_chart(stored_data_json):
    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split') if stored_data_json.get('sales') else pd.DataFrame()
    if df_sales.empty:
        return pd.DataFrame()
    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'])
    monthly_sales = df_sales.set_index('SaleDate').resample('MS')['TotalPrice'].sum().reset_index()
    monthly_sales['Date_Label'] = monthly_sales['SaleDate'].dt.strftime('%b %Y')
    if len(monthly_sales) > 5:
        monthly_sales = monthly_sales.tail(5)
    return monthly_sales

def calculate_last_5_months_sales_change(stored_data_json):
    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split') if stored_data_json.get('sales') else pd.DataFrame()
    if df_sales.empty:
        return "0", "0%"
    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'])
    today = pd.to_datetime(datetime.now().date())
    five_months_ago_start = today - pd.DateOffset(months=5)
    recent_sales_sum = df_sales[df_sales['SaleDate'] >= five_months_ago_start]['TotalPrice'].sum()
    ten_months_ago_start = today - pd.DateOffset(months=10)
    previous_period_sales_sum = df_sales[(df_sales['SaleDate'] >= ten_months_ago_start) & (df_sales['SaleDate'] < five_months_ago_start)]['TotalPrice'].sum()
    
    percentage_change = 0
    if previous_period_sales_sum > 0:
        percentage_change = ((recent_sales_sum - previous_period_sales_sum) / previous_period_sales_sum) * 100
    elif recent_sales_sum > 0: # Handle case where previous period sales were 0
        percentage_change = 100 
    return f"{recent_sales_sum:,.0f}", f"{percentage_change:+.0f}%"

def get_top_categories_in_profit(stored_data_json, top_n=5):
    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split') if stored_data_json.get('sales') else pd.DataFrame()
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()
    
    if df_sales.empty or df_products.empty:
        return pd.DataFrame(), 0

    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'])
    
    
    product_cols_to_merge = ['ProductID', 'Category', 'Cost']
    existing_product_cols = [col for col in product_cols_to_merge if col in df_products.columns]
    
    if len(existing_product_cols) < len(product_cols_to_merge):
        return pd.DataFrame(), 0 

    df_merged = pd.merge(df_sales, df_products[existing_product_cols], 
                         on='ProductID', how='left')
    
    
    df_merged['Cost'] = pd.to_numeric(df_merged['Cost'], errors='coerce').fillna(0)
    df_merged['Quantity'] = pd.to_numeric(df_merged['Quantity'], errors='coerce').fillna(0)
    df_merged['TotalPrice'] = pd.to_numeric(df_merged['TotalPrice'], errors='coerce').fillna(0)
    
    df_merged['Category'] = df_merged['Category'].fillna('Unknown') 

    df_merged['Profit'] = df_merged['TotalPrice'] - (df_merged['Quantity'] * df_merged['Cost'])

    df_merged = df_merged.dropna(subset=['Profit'])
    
    if df_merged.empty:
        return pd.DataFrame(), 0

   
    today = datetime.now() 
    current_quarter_start = today - timedelta(days=90)
    
    df_quarterly_profit_data = df_merged[
        (df_merged['SaleDate'] >= current_quarter_start)
    ].copy() 
    
    
    if df_quarterly_profit_data.empty:
        return pd.DataFrame(), 0

    
    total_profit_current_quarter = df_quarterly_profit_data['Profit'].sum() 

    
    category_profit = df_quarterly_profit_data.groupby('Category')['Profit'].sum().nlargest(top_n).reset_index()
    category_profit.columns = ['Category', 'Profit']
    
    
    category_profit = category_profit[category_profit['Profit'] > 0]
    
    return category_profit, total_profit_current_quarter

def get_notifications(stored_data_json):
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()
    notifications = []

    if not df_products.empty and 'ExpiryDate' in df_products.columns:
        df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')

    today = pd.to_datetime(datetime.now().date())
    
    # Dynamic: Expiring products (top 2)
    expiring_soon_products = df_products[
        (df_products['ExpiryDate'].notna()) &
        (df_products['ExpiryDate'] >= today) &
        (df_products['ExpiryDate'] <= today + timedelta(days=7))
    ].head(2) # Limit to a few to avoid overwhelming notifications
    for _, row in expiring_soon_products.iterrows():
        days_left = (row['ExpiryDate'] - today).days
        notifications.append({
            'type': 'expiring',
            'text': f"Item {row['ProductName']} expiring in {days_left} days!",
            'time': f"{days_left} days left"
        })


    # Static notifications (ensure they are not duplicated if the function is called multiple times)
    notifications.append({'type': 'new_supplier', 'text': "New supplier 'Tech Solutions Inc.' onboarding required.", 'time': "6 hours ago"})
    notifications.append({'type': 'waste', 'text': "Waste report for Q1 needs review.", 'time': "1 day ago"})
    notifications.append({'type': 'low_stock', 'text': "Item XYZ is low in stock: 10 units left!", 'time': "3m ago"})
    notifications.append({'type': 'pending_invoice', 'text': "New supplier ABC has pending invoice.", 'time': "1h ago"})

    return notifications

def get_monthly_waste_data_for_chart(stored_data_json, num_months=3): 
    """
    Calculates monthly waste data for the bar chart, showing the last 'num_months' months.
    Labels months as Jan, Feb, etc.
    """
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()

    if df_products.empty:
        return {'months': [], 'waste_kilos': [], 'df': pd.DataFrame({'Month': [], 'Waste_KGS': []})}

    df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')
    today = pd.to_datetime(datetime.now().date())
    
    # Filter for items that have expired before 'today'
    expired_items = df_products[
        (df_products['ExpiryDate'].notna()) &
        (df_products['ExpiryDate'] < today)
    ].copy()

    if expired_items.empty:
        return {'months': [], 'waste_kilos': [], 'df': pd.DataFrame({'Month': [], 'Waste_KGS': []})}

    
    expired_items['ExpiryMonth'] = expired_items['ExpiryDate'].dt.to_period('M')
    monthly_waste = expired_items.groupby('ExpiryMonth')['Weight'].sum().reset_index()
    monthly_waste.columns = ['MonthPeriod', 'Waste_KGS']

    
    end_month = today.to_period('M')
    all_periods = pd.period_range(end=end_month, periods=2 * num_months, freq='M')

    full_monthly_data = pd.DataFrame({'MonthPeriod': all_periods})
    full_monthly_data = pd.merge(full_monthly_data, monthly_waste, on='MonthPeriod', how='left').fillna(0)
    
    
    display_df = full_monthly_data.tail(num_months).copy()
    
    
    display_df['Month'] = display_df['MonthPeriod'].dt.strftime('%b')

    return {
        'months': display_df['Month'].tolist(),
        'waste_kilos': display_df['Waste_KGS'].tolist(),
        'df': display_df[['Month', 'Waste_KGS']]
    }

def calculate_overall_quarterly_waste(stored_data_json): # Renamed function
    """
    Calculates the total waste for the last 3 months (quarter) and its change from the previous 3 months.
    This is used for the summary text.
    """
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()

    if df_products.empty:
        return {'total_waste_text': "0 kgs", 'change_text': "0%"}

    df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')
    today = pd.to_datetime(datetime.now().date())
    
    expired_items = df_products[
        (df_products['ExpiryDate'].notna()) &
        (df_products['ExpiryDate'] < today)
    ].copy()

    if expired_items.empty:
        return {'total_waste_text': "0 kgs", 'change_text': "0%"}

    # Calculate waste for the last 3 months (current quarter)
    end_date_current = today
    start_date_current = end_date_current - pd.DateOffset(months=3) # 3 months for a quarter
    
    current_period_waste = expired_items[
        (expired_items['ExpiryDate'] >= start_date_current) &
        (expired_items['ExpiryDate'] < end_date_current)
    ]['Weight'].sum()

    # Calculate waste for the previous 3 months (previous quarter)
    end_date_previous = start_date_current
    start_date_previous = end_date_previous - pd.DateOffset(months=3) # Previous 3 months

    previous_period_waste = expired_items[
        (expired_items['ExpiryDate'] >= start_date_previous) &
        (expired_items['ExpiryDate'] < end_date_previous)
    ]['Weight'].sum()

    waste_change_percent = 0
    if previous_period_waste > 0:
        waste_change_percent = ((current_period_waste - previous_period_waste) / previous_period_waste) * 100
    else:
        waste_change_percent = 100 if current_period_waste > 0 else 0

    total_waste_text = f"{current_period_waste:,.0f} kgs"
    change_text = f"{waste_change_percent:+.0f}%"

    return {'total_waste_text': total_waste_text, 'change_text': change_text}


def get_expiry_data(stored_data_json, view_filter='All'):
    print(f"get_expiry_data received view_filter: {view_filter}")
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()
    
    if df_products.empty:
        return pd.DataFrame(), {'expired': '0', 'expiring_7': '0 (0 units)', 'expiring_30': '0 (0 units)'}
    

    df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')
    today = pd.to_datetime(datetime.now().date())

    # Calculate expiry statuses
    df_products['Status'] = 'Good'
    df_products.loc[df_products['ExpiryDate'] < today, 'Status'] = 'Expired'
    df_products.loc[(df_products['Status'] != 'Expired') & 
                    (df_products['ExpiryDate'] >= today) & 
                    (df_products['ExpiryDate'] <= today + timedelta(days=7)), 
                    'Status'] = 'Expiring Soon'
    
     # Logic for 'X Days Remaining'
    nearing_expiry_mask = (df_products['Status'] != 'Expired') & \
                          (df_products['Status'] != 'Expiring Soon') & \
                          (df_products['ExpiryDate'] > today + timedelta(days=7)) & \
                          (df_products['ExpiryDate'] <= today + timedelta(days=30))
    
    # Calculate days remaining for products that fit this mask
    # Ensure to convert ExpiryDate and today to date for accurate day difference, then to timedelta
    days_remaining_series = (df_products.loc[nearing_expiry_mask, 'ExpiryDate'].dt.date - today.date()).apply(lambda x: x.days)

    # Update the 'Status' column with the exact days remaining 
    df_products.loc[nearing_expiry_mask, 'Status'] = 'Nearing Expiry (' + days_remaining_series.astype(str) + ' Days)'
    # --- END Status Calculation ---

  # --- Filtering Logic ---
    display_df = df_products.copy()

    if view_filter == 'Expired': 
        display_df = display_df[display_df['Status'] == 'Expired']
    elif view_filter == 'Expiring Soon': # Includes both 'Expiring Soon' AND 'Nearing Expiry (X Days)'
        display_df = display_df[
            (display_df['Status'] == 'Expiring Soon') | 
            (display_df['Status'].str.contains('Nearing Expiry \\(', na=False)) # ESCAPED PARENTHESIS
        ]
    elif view_filter == 'Expiring in 30 Days': # ONLY includes 'Nearing Expiry (X Days)'
        display_df = display_df[display_df['Status'].str.contains('Nearing Expiry \\(', na=False)] # ESCAPED PARENTHESIS
    elif view_filter == 'All Items': 
        display_df = df_products.copy() 
    # --- END Filtering Logic ---


    # Format ExpiryDate for display
    display_df['ExpiryDate'] = display_df['ExpiryDate'].dt.strftime('%d %b %Y')

    # Prepare data for the table
    table_data = display_df[['ProductName', 'ProductID', 'quantity', 'ExpiryDate', 'Status']].rename(columns={
        'ProductName': 'PRODUCT NAME',
        'ProductID': 'STOCK ID',
        'quantity': 'QUANTITY',
        'ExpiryDate': 'EXPIRY DATE',
        'Status': 'STATUS'
    })

    # Calculate expiry overview metrics
    expired_count = df_products[df_products['Status'] == 'Expired'].shape[0]
    expired_units = df_products[df_products['Status'] == 'Expired']['quantity'].sum()

    expiring_7_count = df_products[df_products['Status'] == 'Expiring Soon'].shape[0]
    expiring_7_units = df_products[df_products['Status'] == 'Expiring Soon']['quantity'].sum()

    expiring_30_count = df_products[
        (df_products['Status'] == 'Expiring Soon') | 
        (df_products['Status'].str.contains('Nearing Expiry \\(', na=False)) 
    ].shape[0]
    expiring_30_units = df_products[
        (df_products['Status'] == 'Expiring Soon') | 
        (df_products['Status'].str.contains('Nearing Expiry \\(', na=False)) 
    ]['quantity'].sum()

    expiry_overview = {
        'expired': f"{expired_count} item{'s' if expired_count != 1 else ''} ({expired_units} units)",
        'expiring_7': f"{expiring_7_count} item{'s' if expiring_7_count != 1 else ''} ({expiring_7_units} units)",
        'expiring_30': f"{expiring_30_count} item{'s' if expiring_30_count != 1 else ''} ({expiring_30_units} units)"
    }

    return table_data, expiry_overview


def calculate_reorder_qty_placeholder(product_id, current_stock, reorder_point, status, demand_proxy, lead_time_days, safety_stock_factor):
    """
    A placeholder function to simulate AI/ML logic for recommended quantity.
    Calculates based on estimated demand during lead time + safety stock.
    """
    daily_demand = demand_proxy.get(product_id, 0)
    lead_time_demand = daily_demand * lead_time_days
    safety_stock = lead_time_demand * safety_stock_factor
    target_stock = lead_time_demand + safety_stock

    if status == 'Out of Stock':
        recommended = max(50, target_stock)
    elif status == 'Low Stock':
        recommended = target_stock - current_stock
        if recommended <= 0:
            recommended = reorder_point - current_stock + max(10, safety_stock)
    elif status == 'Expiring Soon':
        if current_stock < reorder_point:
            recommended = max(20, reorder_point - current_stock + safety_stock)
        else:
            recommended = 0
    else:
        recommended = 0

    return max(0, recommended)



# --- Layout Components ---

sidebar = html.Div(
    [
        html.Div(
            [
                html.Img(src="/assets/invai_logo.png", className="sidebar-logo"),
                html.H2("InvAI", className="sidebar-title"),
                html.P("The Brain Behind Your Inventory", className="sidebar-subtitle"),
            ],
            className="sidebar-header"
        ),
        dbc.Nav(
            [
                dbc.NavLink([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"], href="/", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-box-seam me-2"), "Stock Management"], href="/stock-management", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-arrow-repeat me-2"), "Reorder Recommendations"], href="/reorder-recommendations", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-calendar-x me-2"), "Expiry Management"], href="/expiry-management", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-clipboard-data me-2"), "Scenario Planner"], href="/scenario-planner", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-graph-up me-2"), "Sales & Trends Report"], href="/sales-trends", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-recycle me-2"), "Sustainability Tracker"], href="/sustainability", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-truck me-2"), "Supplier"], href="/supplier", active="exact", className="nav-link-item"),
                dbc.NavLink([html.I(className="bi bi-gear me-2"), "Settings"], href="/settings", active="exact", className="nav-link-item"),
            ],
            vertical=True,
            pills=True,
            className="sidebar-nav"
        ),
        html.Div(
            [
                html.A([html.I(className="bi bi-box-arrow-right me-2"), "Logout"], href="/logout", className="logout-link"),
            ],
            className="sidebar-footer"
        )
    ],
    className="sidebar"
)

# Dashboard Content
dashboard_content = html.Div(
    [
        html.Div(
            [
                html.H3("Dashboard Overview", className="dashboard-header-title"),
                html.Img(src="/assets/user_avatar.png", className="user-avatar")
            ],
            className="dashboard-header"
        ),
        dbc.Card(
            [
                html.Div(
                    [
                        html.H4("Welcome back, Sarah!", className="welcome-banner-title"),
                        html.P("Efficiently manage your stock with smart, sustainable insights", className="welcome-banner-subtitle"),
                        dbc.Button("Explore Dashboard", className="welcome-banner-button"),
                    ],
                    className="welcome-banner-text"
                )
            ],
            className="welcome-banner",
            style={'background-image': 'url("/assets/welcome_banner_bg.png")'}
        ),
        html.H4("Real-Time Metrics", className="section-title"),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            html.P("Items In Stock", className="metric-label"),
                            html.Div([
                                html.H3(id="items-in-stock-value", className="metric-value"),
                                html.Span(id="items-in-stock-change", className="metric-change")
                            ], className="d-flex align-items-center"),
                        ],
                        className="metric-card"
                    ),
                    md=4
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            html.P("Reorder Recommendations", className="metric-label"),
                            html.Div([
                                html.H3(id="reorder-recommendations-value", className="metric-value"),
                                html.Span(id="reorder-recommendations-change", className="metric-change")
                            ], className="d-flex align-items-center"),
                        ],
                        className="metric-card"
                    ),
                    md=4
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            html.P("Expiring Items", className="metric-label"),
                            html.Div([
                                html.H3(id="expiring-items-value", className="metric-value"),
                                html.Span(id="expiring-items-change", className="metric-change")
                            ], className="d-flex align-items-center"),
                        ],
                        className="metric-card"
                    ),
                    md=4
                ),
            ],
            className="mb-4"
        ),
        html.H4("Quick Actions", className="section-title"),
        html.Div(
            [
                dbc.Button("Manage Stock", className="quick-action-btn active"),
                dbc.Button("Restocking", className="quick-action-btn"),
                dbc.Button("Analysis", className="quick-action-btn"),
            ],
            className="quick-actions-container mb-4"
        ),

        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Analytics Preview", className="card-title"),
                            html.P("Sales Over Time", className='small-text mb-1'),
                            html.P(id='sales-over-time-summary', className='text-success mb-2'),
                            dcc.Graph(
                                id='sales-over-time-chart',
                                config={'displayModeBar': False},
                                style={'height': '200px'}
                            )
                        ],
                        className="analytics-card"
                    ),
                    lg=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Notifications & Alerts", className="card-title"),
                            html.Div(id="notifications-list", className="notifications-list")
                        ],
                        className="analytics-card notifications-panel"
                    ),
                    lg=6
                ),
            ],
            className="mb-4"
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Top Categories in Profit", className="card-title"),
                            html.P("Current Quarter", id="profit-period-summary", className="text-muted small-text mb-1"),
                            html.H3(id="total-profit-value", className="profit-value mb-3"),
                            html.Div(id="category-profit-bars-container", className="category-profit-bars")
                        ],
                        className="analytics-card"
                    ),
                    lg=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Sustainability Insights", className="card-title"),
                            html.P("Monthly Waste Breakdown", className="small-text mb-1"), # Clarified for chart
                            html.H3(id='total-waste-kgs', className='waste-main-value mb-2'),
                            html.P(id='monthly-waste-change-summary', className='waste-value small-text mb-3'),
                            dcc.Graph(
                                id='monthly-waste-chart',
                                config={'displayModeBar': False},
                                style={'height': '150px'}
                            )
                        ],
                        className="analytics-card"
                    ),
                    lg=6
                ),
            ],
            className="mb-4"
        ),
    ],
    className="content"
)


# Expiry Management Page Content
expiry_management_content = html.Div(
    [
        html.Div(
            [
                html.H3("Expiry Management", className="dashboard-header-title"),
                html.P("Track and manage products approaching their expiry dates.", className="text-muted"),
                html.Img(src="/assets/user_avatar.png", className="user-avatar")
            ],
            className="dashboard-header"
        ),
        dbc.Card(
            [
                html.Div(
                    [
                        html.H5("Items Nearing Expiration", className="card-title"),
                        html.Div(
                            [
                                html.Span("View: ", className="me-2"),
                                dcc.Dropdown(
                                    id='expiry-view-dropdown',
                                    options=[
                                        {'label': 'All', 'value': 'All'},
                                        {'label': 'Expiring Soon', 'value': 'Expiring Soon'},
                                        {'label': 'Expired', 'value': 'Expired'}
                                    ],
                                    value='All',
                                    clearable=False,
                                    style={'width': '150px', 'display': 'inline-block', 'verticalAlign': 'middle'}
                                )
                            ],
                            className="d-flex align-items-center justify-content-end mb-3"
                        ),
                        dash_table.DataTable(
                            id='expiry-table',
                            columns=[
                                    {"name": "PRODUCT NAME", "id": "PRODUCT NAME"},
                                    {"name": "STOCK ID", "id": "STOCK ID"},
                                    {"name": "QUANTITY", "id": "QUANTITY"},
                                    {"name": "EXPIRY DATE", "id": "EXPIRY DATE"},
                                    {"name": "STATUS", "id": "STATUS"},
                                    # THIS IS CRUCIAL: 'presentation': 'markdown'
                                     {"name": "ACTIONS", "id": "ACTIONS"}
                                     
                                ],
                            data=[],
    editable=False, 
    cell_selectable=True, # <<< Enable individual cell selection
    
    page_action='native',
    page_size=10,  # Set this to your desired number of rows (e.g., 10, 15, 20)
    
                            style_table={'overflowX': 'auto', 'minWidth': '100%'},
                            style_header={
                                'backgroundColor': '#f8f9fa',
                                'fontWeight': 'bold',
                                'textAlign': 'left',
                                'borderBottom': '2px solid #e0e0e0',
                                'padding': '12px 15px'
                            },
                            style_data={
                                'whiteSpace': 'normal',
                                'height': 'auto',
                                'textAlign': 'left',
                                'padding': '10px 15px',
                                'borderBottom': '1px solid #e0e0e0'
                            },
                            style_cell={
                                'fontFamily': 'Inter, sans-serif',
                                'fontSize': '14px',
                                'color': '#333'
                            },
                             style_data_conditional=[
                {
                    'if': {
                        'filter_query': '{STATUS} = "Expired"',
                        'column_id': 'STATUS'
                    },
                    'backgroundColor': '#dc3545', # Red color for Expired
                    'color': 'white'
                },
                {
                    'if': {
                        'filter_query': '{STATUS} = "Expiring Soon"',
                        'column_id': 'STATUS'
                    },
                    'backgroundColor': '#ffc107', # Yellow/Orange color for Expiring Soon
                    'color': '#343a40'
                },
                { # Rule for 'Nearing Expiry (X Days)' - 
                    'if': {
                        'filter_query': '{STATUS} contains "Nearing Expiry (" && {STATUS} contains " Days)"',
                        'column_id': 'STATUS'
                    },
                    'backgroundColor': '#ffc107', 
                    'color': '#343a40' 
                },
                { 
                    'if': {
                        'filter_query': '{STATUS} = "Good"',
                        'column_id': 'STATUS'
                    },
                    'color': '#27ae60', # Green color for Good
                    'fontWeight': 'bold'
                }
            ],
                            selected_rows=[],
                            css=[
                                {"selector": ".dash-spreadsheet-top-container", "rule": "display:none"}, # Hide default pagination/filter bar if not needed
                                {"selector": ".dash-fixed-content", "rule": "width: 100%;"},
                                {"selector": ".dash-table-container .row", "rule": "margin: 0; flex-wrap: nowrap;"},
                                {"selector": ".dash-table-container .col-md-12", "rule": "width:100%; padding:0;"},
                            ]
                        ),
                        html.Button(
                            [html.I(className="bi bi-plus-circle me-2"), "Add New Item Batch"],
                            id='add-item-batch-button',
                            className='add-item-batch-button mt-4'
                        )
                    ]
                ),
            ],
            className="analytics-card mb-4" # Re-using analytics-card style
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Expiry Overview", className="card-title"),
                            html.Div(
                                [
                                    html.P("Expired Items:", className="expiry-overview-label"),
                                    html.P(id="expired-items-count", className="expiry-overview-value text-danger"),
                                ], className="expiry-overview-item"
                            ),
                            html.Div(
                                [
                                    html.P("Expiring in 7 Days:", className="expiry-overview-label"),
                                    html.P(id="expiring-7-days-count", className="expiry-overview-value text-warning"),
                                ], className="expiry-overview-item"
                            ),
                            html.Div(
                                [
                                    html.P("Expiring in 30 Days:", className="expiry-overview-label"),
                                    html.P(id="expiring-30-days-count", className="expiry-overview-value text-info"),
                                ], className="expiry-overview-item"
                            ),
                        ],
                        className="analytics-card"
                    ),
                    lg=6
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            html.H5("Quick Actions", className="card-title"),
                            dbc.Button("Generate Expiry Report", id="generate-expiry-report-btn", className="quick-action-btn-expiry"),
                            dbc.Button("Set Notifications", id="set-notifications-btn", className="quick-action-btn-expiry"),
                        ],
                        className="analytics-card d-flex flex-column justify-content-start"
                    ),
                    lg=6
                ),
            ],
            className="mb-4"
        ),
    ],
    className="content"
)


# Main App Layout
app.layout = html.Div([
    dcc.Store(id='stored-data', data=app_data),
    dcc.Location(id='url', refresh=False),
    
    # --- NEW: Stores for time aggregation state ---
    dcc.Store(id='sales-time-agg-state', data='Monthly'),  # Default to Monthly
    dcc.Store(id='profit-time-agg-state', data='Monthly'), # Default to Monthly
    # --- END NEW ---
    
    sidebar,
    html.Div(id='page-content', className="content-container") # This will hold the dynamic content
], className="app-container")


# --- Callbacks ---

@app.callback(
    Output('page-content', 'children'),
    Output('page-content', 'className'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    # Initialize default values
    page_layout = html.Div([html.H1("404: Not found"), html.P(f"The pathname {pathname} was not recognised...")])
    content_class = "content-container" # Default class for all pages

    if pathname == '/expiry-management':
        page_layout = expiry_management_content
    elif pathname == '/':
        page_layout = dashboard_content
    elif pathname == '/stock-management':
        page_layout = stock_management_content
    elif pathname == '/reorder-recommendations':
        page_layout = reorder_recommendations_layout
        content_class = "content-container reorder-recommendations-layout-fix"
    elif pathname == '/supplier':
        page_layout = supplier_management_layout
        content_class = "content"
    elif pathname == '/sales-trends':
        page_layout = sales_trends_layout
        content_class = "content-container p-4"
    elif pathname == '/sustainability':
        page_layout = sustainability_layout
        content_class = "sustainability-content"
        
    return page_layout, content_class

@app.callback(
    [
        Output('items-in-stock-value', 'children'),
        Output('items-in-stock-change', 'children'),
        Output('items-in-stock-change', 'className'),
        Output('reorder-recommendations-value', 'children'),
        Output('reorder-recommendations-change', 'children'),
        Output('reorder-recommendations-change', 'className'),
        Output('expiring-items-value', 'children'),
        Output('expiring-items-change', 'children'),
        Output('expiring-items-change', 'className'),
    ],
    Input('stored-data', 'data')
)
def update_realtime_metrics(data):
    metrics = get_realtime_metrics(data)
    stock_class = f"metric-change {metrics['stock_change_class']}"
    reorder_class = f"metric-change {metrics['reorder_change_class']}"
    expiring_class = f"metric-change {metrics['expiring_change_class']}"
    return (
        metrics['items_in_stock'], html.Span([html.I(className="bi bi-arrow-up-right"), metrics['stock_change']]), stock_class,
        metrics['reorder_recommendations'], html.Span([html.I(className="bi bi-arrow-up-right"), metrics['reorder_change']]), reorder_class,
        html.Span(metrics['expiring_items']), html.Span([html.I(className="bi bi-arrow-down-right"), metrics['expiring_change']]), expiring_class
    )

@app.callback(
    [Output('sales-over-time-chart', 'figure'),
     Output('sales-over-time-summary', 'children')],
    [Input('stored-data', 'data')]
)
def update_sales_chart(data):
    monthly_sales = get_sales_data_for_chart(data)
    total_sales_str, percentage_change_str = calculate_last_5_months_sales_change(data)

    if monthly_sales.empty:
        fig = go.Figure()
    else:
        fig = px.line(monthly_sales, x='SaleDate', y='TotalPrice', markers=True,
                      line_shape='linear',
                      color_discrete_sequence=['#1abc9c'])

        fig.update_xaxes(
            tickvals=monthly_sales['SaleDate'],
            ticktext=monthly_sales['SaleDate'].dt.strftime('%b'),
            showgrid=False, showline=False, zeroline=False
        )
        fig.update_yaxes(
            showgrid=True, gridcolor='#e0e0e0', showline=False, zeroline=False, showticklabels=True
        )

    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title=None, yaxis_title=None,
        hovermode='x unified', font=dict(family="Inter, sans-serif")
    )
    summary_text = f"₹{total_sales_str} Last 5 Months {percentage_change_str}"
    return fig, summary_text

@app.callback(
    [Output('total-profit-value', 'children'),
     Output('category-profit-bars-container', 'children')],
    [Input('stored-data', 'data')]
)
def update_profit_categories(data):
    category_profit, total_profit = get_top_categories_in_profit(data)
    total_profit_formatted = f"₹{total_profit:,.0f}"
    bars_children = []

    # Check if category_profit DataFrame is empty or contains only zero profit
    if category_profit.empty or total_profit == 0:
        bars_children.append(
            html.Div(
                "No profit data available for the current quarter or categories.",
                style={'textAlign': 'center', 'padding': '20px', 'color': '#888'}
            )
        )
        total_profit_formatted = "₹0" # Ensure total profit also shows zero
    else:
        max_profit = category_profit['Profit'].max()
        # Ensure max_profit is not zero to avoid division by zero
        max_profit = max_profit if max_profit > 0 else 1 

        for index, row in category_profit.iterrows():
            percentage = (row['Profit'] / max_profit) * 100
            bars_children.append(
                html.Div(className='category-bar-item', children=[
                    html.Span(row['Category'], className='category-name'),
                    html.Span(f"₹{row['Profit']:,.0f}", className='category-value'),
                    html.Div(className='category-bar-background', children=[
                        html.Div(className='category-bar-fill', style={'width': f'{percentage}%'})
                    ])
                ])
            )
    return total_profit_formatted, bars_children

@app.callback(
    Output('notifications-list', 'children'),
    Input('stored-data', 'data')
)
def update_notifications(data):
    notifications = get_notifications(data)
    notification_elements = []
    for notification in notifications:
        icon_class = ""
        if notification['type'] == 'expiring':
            icon_class = "bi bi-exclamation-triangle-fill text-warning"
        elif notification['type'] == 'new_supplier':
            icon_class = "bi bi-person-plus-fill text-info"
        elif notification['type'] == 'waste':
            icon_class = "bi bi-trash-fill text-success"
        elif notification['type'] == 'low_stock':
            icon_class = "bi bi-box-fill text-danger"
        elif notification['type'] == 'pending_invoice':
            icon_class = "bi bi-file-earmark-text text-warning"
        notification_elements.append(
            html.Div(
                [
                    html.Div([html.I(className=f"notification-icon {icon_class}"), html.Span(notification['text'], className="notification-text")]),
                    html.Span(notification['time'], className="notification-time")
                ],
                className="notification-item"
            )
        )
    return notification_elements

@app.callback(
    [Output('monthly-waste-chart', 'figure'),
     Output('total-waste-kgs', 'children'),
     Output('monthly-waste-change-summary', 'children')],
    [Input('stored-data', 'data')]
)
def update_sustainability_insights(data):
    # Get overall quarterly waste for the summary text
    overall_waste_summary = calculate_overall_quarterly_waste(data) # Calling the new quarterly function
    total_waste_text = overall_waste_summary['total_waste_text']
    waste_change_text = overall_waste_summary['change_text']

    # Get monthly waste data for the bar chart (last 3 months for the quarter)
    monthly_data_for_chart = get_monthly_waste_data_for_chart(data, num_months=3) # Requesting 3 months for the chart
    waste_df_monthly = monthly_data_for_chart['df']

    if waste_df_monthly.empty:
        fig = go.Figure()
    else:
        fig = px.bar(waste_df_monthly, x='Month', y='Waste_KGS', # 'Month' column contains 'Feb', 'Mar', etc.
                     color_discrete_sequence=['#a0d9b4'])

        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis_title=None, yaxis_title=None,
            xaxis=dict(showgrid=False, showline=False, zeroline=False),
            yaxis=dict(showgrid=False, showline=False, zeroline=False, showticklabels=False),
            hovermode='x unified', font=dict(family="Inter, sans-serif")
        )
        fig.update_traces(marker_line_width=0)

    # The summary text now indicates "Last Quarter"
    return fig, total_waste_text, f"Last Quarter {waste_change_text}"


# Callbacks for Expiry Management Page
@app.callback(
    [Output('expiry-table', 'data'),
     Output('expired-items-count', 'children'),
     Output('expiring-7-days-count', 'children'),
     Output('expiring-30-days-count', 'children')],
    [Input('stored-data', 'data'),
     Input('expiry-view-dropdown', 'value')]
)
def update_expiry_data(data, view_filter):
    table_data_df, expiry_overview_metrics = get_expiry_data(data, view_filter)

    # Convert DataFrame to a list of dictionaries (records)
    records = table_data_df.to_dict('records')

    # --- SIMPLIFIED ACTIONS COLUMN: Just a string for the cell ---
    for row in records:
        # We can put a string that guides the user to click for actions
        row['ACTIONS'] = "Discount | Dispose"
    
    return (
        records,
        expiry_overview_metrics['expired'],
        expiry_overview_metrics['expiring_7'],
        expiry_overview_metrics['expiring_30']
    )
    
   # --- Callback to handle cell clicks (modified slightly for clarity) ---
@app.callback(
    Output('some-output-div', 'children'), # Make sure this div exists in your layout
    Input('expiry-table', 'active_cell'),
    State('expiry-table', 'data')
)
def handle_action_cell_click(active_cell, table_data):
    print("Active Cell:", active_cell) # Keep this for debugging in your terminal
    if active_cell:
        row_id = active_cell['row']
        column_id = active_cell['column_id']
        # The value will be "[Discount](javascript:void(0)) | [Dispose](javascript:void(0))"

        if column_id == 'ACTIONS':
            clicked_row_data = table_data[row_id]
            stock_id = clicked_row_data['STOCK ID']

            
            return html.Div([
                html.P(f"Action requested for Stock ID: {stock_id}."),
                html.P("What action do you want to perform?"),
                dbc.Button("Discount This Item", id={'type': 'final-action-btn', 'action': 'discount', 'stock_id': stock_id}, color="success", className="me-2"),
                dbc.Button("Dispose This Item", id={'type': 'final-action-btn', 'action': 'dispose', 'stock_id': stock_id}, color="danger")
            ])
            
    return ""

# --- Stock Management Page Content ---
stock_management_content = html.Div(
    [
        html.Div(
            [
                html.H3("Stock Management", className="dashboard-header-title"),
                html.P("Manage your stock levels, add new items, and update existing items. All weight-based units are in kilograms (kgs).", className="text-muted"),
                html.Img(src="/assets/user_avatar.png", className="user-avatar")
            ],
            className="dashboard-header"
        ),
        dbc.Card(
            [
                html.Div(
                    [
                        dbc.Button(
                            [html.I(className="bi bi-upload me-2"), "Upload Data"],
                            id="upload-data-btn",
                            className="upload-data-btn mb-4"
                        ),
                        # Search Bar
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText(html.I(className="bi bi-search")),
                                dbc.Input(id="stock-search-input", placeholder="Search for items by name, SKU, or supplier...", type="text", className="search-input")
                            ],
                            className="mb-4"
                        ),
                        # Filter Dropdowns
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Dropdown(
                                        id='stock-category-filter',
                                        options=[{'label': 'All Categories', 'value': 'all'}],
                                        value='all',
                                        placeholder="Category",
                                        clearable=False,
                                        className="filter-dropdown"
                                    ),
                                    md=4
                                ),
                                dbc.Col(
                                    dcc.Dropdown(
                                        id='stock-supplier-filter',
                                        options=[{'label': 'All Suppliers', 'value': 'all'}],
                                        value='all',
                                        placeholder="Supplier",
                                        clearable=False,
                                        className="filter-dropdown"
                                    ),
                                    md=4
                                ),
                                dbc.Col(
                                    dcc.Dropdown(
                                        id='stock-status-filter',
                                        options=[
                                            {'label': 'All Statuses', 'value': 'all'},
                                            {'label': 'In Stock', 'value': 'In Stock'},
                                            {'label': 'Low Stock', 'value': 'Low Stock'},
                                            {'label': 'Out of Stock', 'value': 'Out of Stock'}
                                        ],
                                        value='all',
                                        placeholder="Status",
                                        clearable=False,
                                        className="filter-dropdown"
                                    ),
                                    md=4
                                ),
                            ],
                            className="mb-4"
                        ),
                        # Stock Table
                        dash_table.DataTable(
                            id='stock-table',
                            columns=[
                                {"name": "ITEM NAME", "id": "ITEM NAME"},
                                {"name": "QUANTITY", "id": "QUANTITY"},
                                {"name": "SUPPLIER", "id": "SUPPLIER"},
                                {"name": "CATEGORY", "id": "CATEGORY"},
                                {"name": "STATUS", "id": "STATUS"},
                                {"name": "ACTIONS", "id": "ACTIONS", "presentation": "markdown"},
                                
                            ],

                            data=[],
                            editable=False,
                            page_action='native',
                            page_size=10,
                            sort_action="native",
                            filter_action="none",
                            markdown_options={"html": True},
                            style_table={'overflowX': 'auto', 'minWidth': '100%'},
                            style_header={
                                'backgroundColor': '#f8f9fa',
                                'fontWeight': 'bold',
                                'textAlign': 'left',
                                'borderBottom': '2px solid #e0e0e0',
                                'padding': '12px 15px'
                            },
                            style_data={
                                'whiteSpace': 'normal',
                                'height': 'auto',
                                'textAlign': 'left',
                                'padding': '10px 15px',
                                'borderBottom': '1px solid #e0e0e0'
                            },
                            style_cell={
                                'fontFamily': 'Inter, sans-serif',
                                'fontSize': '14px',
                                'color': '#333'
                            },
                            style_data_conditional=[
                                {
                                    'if': {'column_id': 'STATUS', 'filter_query': '{STATUS} = "In Stock"'},
                                    'color': '#27ae60',
                                    'fontWeight': 'bold'
                                },
                                {
                                    'if': {'column_id': 'STATUS', 'filter_query': '{STATUS} = "Low Stock"'},
                                    'color': '#f39c12',
                                    'fontWeight': 'bold'
                                },
                                {
                                    'if': {'column_id': 'STATUS', 'filter_query': '{STATUS} = "Out of Stock"'},
                                    'color': '#e74c3c',
                                    'fontWeight': 'bold'
                                },
                                {
                                    'if': {'column_id': 'ACTIONS'},
                                    'textAlign': 'center',
                                    'padding': '0',
                                },
                            ],
                            css=[
                                {"selector": ".dash-spreadsheet-top-container", "rule": "display:none"},
                                {"selector": ".dash-fixed-content", "rule": "width: 100%;"},
                                {"selector": ".dash-table-container .row", "rule": "margin: 0; flex-wrap: nowrap;"},
                                {"selector": ".dash-table-container .col-md-12", "rule": "width:100%; padding:0;"},
                            ]
                        )
                    ]
                )
            ],
            className="analytics-card mb-4"
        ),
        # --- NEW MODAL FOR STOCK PRODUCT DETAILS ---
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Product Details")),
                dbc.ModalBody(id="stock-product-details-body"), # Content will go here
                dbc.ModalFooter(
                    dbc.Button(
                        "Close", id="close-stock-details-modal", className="ms-auto", n_clicks=0
                    )
                ),
            ],
            id="stock-details-modal",
            is_open=False, # Hidden by default
            size="lg",
            centered=True,
        ),
        # --- END NEW MODAL ---
    ],
    className="content"
)


# --- Helper Function for Stock Management Data ---
def get_stock_data(stored_data_json, search_term='', category_filter='all', supplier_filter='all', status_filter='all'):
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()

    if df_products.empty:
        print("df_products is empty in get_stock_data.")
        return pd.DataFrame().to_dict('records')

    # Ensure 'ProductID' is available early
    if 'ProductID' not in df_products.columns:
        print("Warning: 'ProductID' column not found, 'STOCK ID' cannot be generated. Returning empty.")
        return pd.DataFrame().to_dict('records')

    # Ensure 'quantity' is numeric (important for calculations and comparisons)
    if 'quantity' in df_products.columns:
        df_products['quantity'] = pd.to_numeric(df_products['quantity'], errors='coerce').fillna(0)
    else:
        print("Warning: 'quantity' column not found in df_products. Returning empty.")
        return pd.DataFrame().to_dict('records')

    # Ensure 'SupplierName' is renamed to 'Supplier' if coming directly from CSV
    # This part should ideally be in load_data(), but adding here as a safeguard if not.
    if 'SupplierName' in df_products.columns and 'Supplier' not in df_products.columns:
        df_products = df_products.rename(columns={'SupplierName': 'Supplier'})
    elif 'Supplier' not in df_products.columns:
        print("Warning: Neither 'SupplierName' nor 'Supplier' column found. Returning empty.")
        return pd.DataFrame().to_dict('records')

    # --- Calculate Stock Status ---
    LOW_STOCK_THRESHOLD = 20
    OUT_OF_STOCK_THRESHOLD = 0

    df_products['STATUS'] = 'In Stock' # Default status
    df_products.loc[df_products['quantity'] <= OUT_OF_STOCK_THRESHOLD, 'STATUS'] = 'Out of Stock'
    df_products.loc[(df_products['quantity'] > OUT_OF_STOCK_THRESHOLD) & (df_products['quantity'] <= LOW_STOCK_THRESHOLD), 'STATUS'] = 'Low Stock'
    
    # --- Add ACTIONS column (Must be a Markdown string for DataTable rendering) ---
    # This markdown string will render as a clickable link.
    df_products['ACTIONS'] = "View" # Corrected to Markdown link

    # --- Apply Filters ---
    # IMPORTANT: filtered_df must be created *after* all necessary columns (like STATUS, ACTIONS) are added to df_products
    filtered_df = df_products.copy()

    # Search by Item Name, Product ID (SKU), Supplier
    if search_term:
        search_term_lower = search_term.lower()
        filtered_df = filtered_df[
            filtered_df['ProductName'].str.lower().str.contains(search_term_lower, na=False) |
            filtered_df['ProductID'].astype(str).str.lower().str.contains(search_term_lower, na=False) |
            filtered_df['Supplier'].str.lower().str.contains(search_term_lower, na=False)
        ]

    # Category Filter
    if category_filter != 'all':
        filtered_df = filtered_df[filtered_df['Category'] == category_filter]

    # Supplier Filter
    if supplier_filter != 'all':
        filtered_df = filtered_df[filtered_df['Supplier'] == supplier_filter]

    # Status Filter
    if status_filter != 'all':
        filtered_df = filtered_df[filtered_df['STATUS'] == status_filter]
    
    # --- Combine Quantity with UnitOfMeasure for display (Moved to after filtering) ---
    # Ensure 'Weight' column exists if needed elsewhere (from previous discussions)
    if 'Weight' not in filtered_df.columns:
        filtered_df['Weight'] = 0.5 # Default weight if not present

    if 'quantity' in filtered_df.columns and 'UnitOfMeasure' in filtered_df.columns:
        filtered_df['DISPLAY_QUANTITY'] = filtered_df['quantity'].astype(str) + ' ' + filtered_df['UnitOfMeasure']
    else:
        filtered_df['DISPLAY_QUANTITY'] = filtered_df['quantity'].astype(str)
        print("Warning: 'UnitOfMeasure' column not found in filtered_df, displaying quantity without units.")
        
        
    
    # --- Prepare data for the table ---
    # Define the required columns for the final DataTable display
    required_cols_for_display = [
        'ProductID', # Included for use in the modal callback via 'STOCK ID'
        'ProductName',
        'DISPLAY_QUANTITY', # Use the new combined quantity + unit column
        'Supplier',
        'Category',
        'STATUS',
        'ACTIONS'
    ]

    # Perform a check if all required columns are present in filtered_df before selection
    for col in required_cols_for_display:
        if col not in filtered_df.columns:
            print(f"Error: Required column '{col}' not found in filtered_df for table display. Returning empty.")
            return pd.DataFrame().to_dict('records')

    # Select and rename columns for DataTable output
    table_data = filtered_df[required_cols_for_display].rename(columns={
        'ProductID': 'STOCK ID', # Renamed for display and internal use (e.g., in modal)
        'ProductName': 'ITEM NAME',
        'DISPLAY_QUANTITY': 'QUANTITY', # Renamed heading to just 'QUANTITY'
        'Supplier': 'SUPPLIER',
        'Category': 'CATEGORY',
    })

    return table_data.to_dict('records') # Return as list of dictionaries

# --- Callbacks for Stock Management Page ---
@app.callback(
    [Output('stock-table', 'data'),
     Output('stock-category-filter', 'options'),
     Output('stock-supplier-filter', 'options')],
    [Input('stored-data', 'data'),
     Input('stock-search-input', 'value'),
     Input('stock-category-filter', 'value'),
     Input('stock-supplier-filter', 'value'),
     Input('stock-status-filter', 'value')]
)
def update_stock_table(data, search_term, category_filter, supplier_filter, status_filter):
    # Get data for the table based on filters
    filtered_stock_data = get_stock_data(data, search_term, category_filter, supplier_filter, status_filter)

    # Get unique categories and suppliers for dropdown options
    df_products = pd.read_json(io.StringIO(data['products']), orient='split') if data.get('products') else pd.DataFrame()
    
    categories = [{'label': 'All Categories', 'value': 'all'}]
    if not df_products.empty and 'Category' in df_products.columns:
        categories.extend([{'label': cat, 'value': cat} for cat in df_products['Category'].unique()])

    suppliers = [{'label': 'All Suppliers', 'value': 'all'}]
    if not df_products.empty and 'Supplier' in df_products.columns:
        suppliers.extend([{'label': sup, 'value': sup} for sup in df_products['Supplier'].unique()])
    
    return filtered_stock_data, categories, suppliers

# --- Callback for 'View' button in Stock Table (using active_cell) ---
@app.callback(
    [Output('stock-details-modal', 'is_open'),
     Output('stock-product-details-body', 'children')],
    [Input('stock-table', 'active_cell'), # <--- CHANGED: Listen to active_cell of the DataTable
     Input('close-stock-details-modal', 'n_clicks')], # Input for closing the modal
    [State('stock-table', 'data'),         # <--- ADDED: State to access the full table data
     State('stock-details-modal', 'is_open')],
    prevent_initial_call=True
)
def toggle_stock_details_modal(active_cell, close_n_clicks, table_data, is_open): # <--- UPDATED ARGUMENTS
    ctx = dash.callback_context

    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]['prop_id']

    # Handle close button click
    if "close-stock-details-modal" in trigger_id and close_n_clicks:
        return False, dash.no_update # Close modal, no update to body

    # Handle active_cell click on the table
    # Check if the trigger was from 'stock-table.active_cell' and if a cell was actually clicked
    if "stock-table.active_cell" in trigger_id and active_cell:
        row_index = active_cell['row']
        column_id = active_cell['column_id']

        # Only proceed if the clicked column is 'ACTIONS'
        if column_id == 'ACTIONS':
            clicked_row_data = table_data[row_index] # Get the data for the clicked row
            stock_id = clicked_row_data.get('STOCK ID', 'N/A') # Get the stock ID from the row data

            # Basic Information
            item_name = clicked_row_data.get('ITEM NAME', 'N/A') # Mapped from ProductName
            category = clicked_row_data.get('CATEGORY', 'N/A')
            supplier_name = clicked_row_data.get('SUPPLIER', 'N/A') # Mapped from SupplierName

            # Get raw numeric quantity and unit of measure for calculations and separate display
            raw_quantity = clicked_row_data.get('StockQuantity', 'N/A')
            unit_of_measure = clicked_row_data.get('UnitOfMeasure', 'N/A')

            # Price and Profitability
            cost_price = clicked_row_data.get('Cost', 'N/A')
            selling_price = clicked_row_data.get('Price', 'N/A')

            # Inventory Details
            minimum_stock = clicked_row_data.get('ReorderPoint', 'N/A')
            last_restocked = 'N/A' # Not in CSV - will be N/A

            # Supplier contact
            phone = 'N/A' # Not in CSV - will be N/A
            email = 'N/A' # Not in CSV - will be N/A

            # --- Calculations for Price and Profitability ---
            profit_margin = 'N/A'
            total_cost_value = 'N/A'
            expected_revenue = 'N/A'
            estimated_profit = 'N/A'

            try:
                numeric_cost = float(cost_price)
                numeric_selling = float(selling_price)
                numeric_quantity = float(raw_quantity)

                if numeric_selling != 0:
                    profit_margin = f"{((numeric_selling - numeric_cost) / numeric_selling) * 100:.2f}%"
                
                total_cost_value = f"₹{numeric_cost * numeric_quantity:.2f}"
                expected_revenue = f"₹{numeric_selling * numeric_quantity:.2f}"
                estimated_profit = f"₹{(numeric_selling - numeric_cost) * numeric_quantity:.2f}"

            except (ValueError, TypeError):
                # If any of the values are not numeric, calculations will remain N/A
                pass

            # --- Construct the modal content based on your detailed list ---
            details_content = html.Div([
                html.H4("Product Details", className="mb-3"), # Main modal title

                # Basic Information
                html.H5("Basic Information", className="mb-2 mt-4"),
                dbc.Row([
                    dbc.Col(html.P(f"Item Name: {item_name}"), width=6),
                    dbc.Col(html.P(f"Category: {category}"), width=6),
                ]),
                dbc.Row([
                    dbc.Col(html.P(f"Supplier: {supplier_name}"), width=6),
                    dbc.Col(html.P(f"Quantity: {raw_quantity} {unit_of_measure}"), width=6), # Displaying numeric quantity with unit
                ]),

                # Price and Profitability
                html.H5("Price and Profitability", className="mb-2 mt-4"),
                dbc.Row([
                    dbc.Col(html.P(f"Cost price: ₹{cost_price}"), width=6),
                    dbc.Col(html.P(f"Selling price: ₹{selling_price}"), width=6),
                ]),
                dbc.Row([
                    dbc.Col(html.P(f"Profit Margin: {profit_margin}"), width=6),
                    dbc.Col(html.P(f"Total cost value: {total_cost_value}"), width=6),
                ]),
                dbc.Row([
                    dbc.Col(html.P(f"Expected revenue: {expected_revenue}"), width=6),
                    dbc.Col(html.P(f"Estimated profit: {estimated_profit}"), width=6),
                ]),

                # Inventory Details
                html.H5("Inventory Details", className="mb-2 mt-4"),
                dbc.Row([
                    dbc.Col(html.P(f"Unit type: {unit_of_measure}"), width=6),
                    dbc.Col(html.P(f"Minimum stock: {minimum_stock}"), width=6),
                ]),
                dbc.Row([
                    dbc.Col(html.P(f"Total quantity: {raw_quantity} {unit_of_measure}"), width=6), # Assuming this is current stock again
                    dbc.Col(html.P(f"Last Restocked: {last_restocked}"), width=6),
                ]),

                # Supplier Contact
                html.H5("Supplier Contact", className="mb-2 mt-4"),
                dbc.Row([
                    dbc.Col(html.P(f"Phone: {phone}"), width=6),
                    dbc.Col(html.P(f"Email: {email}"), width=6),
                ]),
            ])
            # --- End of new modal content construction ---

            return not is_open, details_content
    
    # If no relevant trigger or active_cell is None, prevent update.
    return is_open, dash.no_update


# Reorder Recommendation

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table # Ensure dash_table is imported

# --- REVISED: Layout of the Reorder Recommendations page ---
reorder_recommendations_layout = html.Div(className="main-content-area p-3", children=[
    html.Div(
        className="reorder-table-container card card-body", children=[
            html.H4("Reorder Recommendations", className="card-title"),
            html.P("Based on demand forecasts, current stock levels, and expiry dates.", className="card-text"),
            dash_table.DataTable(
                id='reorder-recommendations-table',
                columns=[
                    {'name': 'PRODUCT', 'id': 'PRODUCT'},
                    {'name': 'SUPPLIER', 'id': 'SUPPLIER'},
                    {'name': 'CURRENT STOCK', 'id': 'CURRENT STOCK', 'type': 'numeric'},
                    {'name': 'LAST REORDER DATE', 'id': 'LAST REORDER DATE'},
                    # This column will now display the actual short reason
                    {'name': 'REASON FOR REORDER', 'id': 'REASON FOR REORDER'},
                    {'name': 'RECOMMENDED QTY', 'id': 'RECOMMENDED QTY', 'type': 'numeric'},
                    {'name': 'ADJUST QUANTITY', 'id': 'ADJUST QUANTITY', 'type': 'numeric', 'editable': True},
                    {'name': 'CYCLIC REORDER', 'id': 'CYCLIC REORDER'},
                    {'name': 'Hidden Detail', 'id': 'REASON_FOR_REORDER_DETAIL_HIDDEN'}
                ],
                data=[], # Data will be populated by callback
                editable=False,
                selected_rows=[],
                page_action='native',
                page_size=10,
                style_table={'overflowX': 'auto', 'minWidth': '100%'},
                style_cell={
                    'minWidth': '80px', 'width': '150px', 'maxWidth': '250px',
                    'whiteSpace': 'normal',
                    'textAlign': 'left',
                    'padding': '10px',
                    'backgroundColor': 'white',
                    'color': '#333',
                    'borderBottom': '1px solid #e9ecef',
                },
                style_header={
                    'backgroundColor': '#f8f9fa',
                    'fontWeight': 'bold',
                    'color': '#333',
                    'borderBottom': '2px solid #dee2e6',
                    'textAlign': 'left',
                    'padding': '10px'
                },
                style_data_conditional=[
                    # --- REVISED: Conditional style for 'REASON FOR REORDER' column ---
                    # Now, make it clickable/underlined IF it's NOT 'Adequate Stock'
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} ne "Adequate Stock"' # Apply if the value is NOT 'Adequate Stock'
                        },
                        'color': '#007bff',          # Bootstrap primary blue
                        'textDecoration': 'underline', # Underline like a link
                        'cursor': 'pointer',         # Show pointer cursor on hover
                        'fontWeight': 'bold'
                    },
                    # Specific styling rules for different short reasons (optional, can be adjusted)
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Critically Low Stock"'
                        },
                        'color': '#e74c3c', # Red
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Expired"'
                        },
                        'color': '#e74c3c', # Red for expired
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Below Reorder Point"'
                        },
                        'color': '#f39c12', # Orange
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Expiring Soon"'
                        },
                        'color': '#f39c12', # Orange
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "High Demand"' # Though this will likely fall under 'AI/ML Recommendation' short reason
                        },
                        'color': '#3498db', # Blue
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Upward Trend"' # Will also likely fall under 'AI/ML Recommendation' short reason
                        },
                        'color': '#2ecc71', # Green
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Consistent High Sales"' # Will also likely fall under 'AI/ML Recommendation' short reason
                        },
                        'color': '#1abc9c', # Turquoise
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "AI/ML Recommendation"'
                        },
                        'color': '#3498db', # Blue (can be different from 'View Details' color)
                        'fontWeight': 'normal'
                    },
                    {
                        'if': {
                            'column_id': 'REASON FOR REORDER',
                            'filter_query': '{REASON FOR REORDER} eq "Adequate Stock"'
                        },
                        'color': '#28a745', # Green
                        'fontWeight': 'normal'
                    }
                ],
                css=[
                    {"selector": ".dash-spreadsheet-container table", "rule": "font-family: 'Inter', sans-serif;"},
                    {"selector": ".dash-header", "rule": "height: 40px;"},
                    {"selector": ".dash-cell", "rule": "height: 35px; overflow: hidden;"},
                    {"selector": ".dash-spreadsheet-container td", "rule": "text-align: left;"},
                    {"selector": ".dash-spreadsheet-container th", "rule": "text-align: left;"},
                ],
                hidden_columns=['REASON_FOR_REORDER_DETAIL_HIDDEN']
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Reorder Details")),
                    dbc.ModalBody(id="modal-body"),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close-modal", className="ms-auto", n_clicks=0)
                    ),
                ],
                id="modal",
                is_open=False,
            )
        ]
    ),
    html.Div(className="d-flex justify-content-end mt-4", children=[
        dbc.Button("Initiate Reordering Process", id="initiate-reorder-process-btn", color="success", size="lg"),
    ])
])

# --- Callbacks for Initial Data Loading (Crucial for all pages, including Reorder) ---
# This callback populates the dcc.Store with data from load_data()
# You must have dcc.Store(id='stored-data') in your app.layout for this to work.
@app.callback(
    Output('stored-data', 'data'),
    Input('url', 'pathname') # Triggered on initial load and URL changes
)
def initialize_stored_data(pathname):
    return load_data()


# --- Global Constants for Demand Analysis (can be moved to config) ---
SHORT_PERIOD_DAYS = 7
LONG_PERIOD_DAYS = 30
VERY_LONG_PERIOD_DAYS = 90
SALES_SPIKE_FACTOR = 1.5
UPWARD_TREND_FACTOR = 1.2
HIGH_VOLUME_THRESHOLD = 5 # units per day for consistent high sales


# Mock functions for demonstration of logic if not already defined in the environment
# These should be replaced by your actual imported functions if running in a full app context.
def calculate_reorder_qty_placeholder(product_id, stock_qty, reorder_point, status_reorder, demand_proxy, avg_lead_time_days, safety_stock_buffer):
    # Simplified placeholder for calculation
    # For core inventory reasons
    if status_reorder == 'Out of Stock':
        return max(50, demand_proxy.get(product_id, 0) * avg_lead_time_days * (1 + safety_stock_buffer) * 2)
    elif status_reorder == 'Expired':
         return max(50, demand_proxy.get(product_id, 0) * avg_lead_time_days * (1 + safety_stock_buffer) * 2) # Assume similar urgency as out of stock
    elif status_reorder == 'Low Stock':
        return max(20, demand_proxy.get(product_id, 0) * avg_lead_time_days * (1 + safety_stock_buffer))
    elif status_reorder == 'Expiring Soon':
        return max(10, demand_proxy.get(product_id, 0) * avg_lead_time_days * (1 + safety_stock_buffer))
    # For demand-driven/AI/ML reasons when stock is 'Adequate'
    else: # This covers 'Adequate' stock with demand-driven reasons
        return max(0, demand_proxy.get(product_id, 0) * avg_lead_time_days * (1 + safety_stock_buffer)) # Ensure positive

# --- Callbacks for Reorder Recommendations Page ---
@app.callback(
    Output('reorder-recommendations-table', 'data'),
    Input('stored-data', 'data')
)
def populate_reorder_table(stored_data_json):
    df_products = pd.read_json(io.StringIO(stored_data_json['products']), orient='split') if stored_data_json.get('products') else pd.DataFrame()
    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split') if stored_data_json.get('sales') else pd.DataFrame()
    df_purchases = pd.read_json(io.StringIO(stored_data_json['purchases']), orient='split') if stored_data_json.get('purchases') else pd.DataFrame()

    if df_products.empty:
        print("df_products is empty in populate_reorder_table.")
        return pd.DataFrame().to_dict('records')

    df_products = df_products.rename(columns={'quantity': 'StockQuantity', 'UnitOfMeasure': 'Unit'})
    df_products = df_products.rename(columns={'Cost': 'CostPricePerKg', 'Price': 'SellingPricePerKg'})

    if not df_purchases.empty and 'ProductID' in df_purchases.columns and 'PurchaseDate' in df_purchases.columns:
        df_purchases['PurchaseDate'] = pd.to_datetime(df_purchases['PurchaseDate'], errors='coerce')
        latest_purchase_dates = df_purchases.groupby('ProductID')['PurchaseDate'].max().reset_index()
        latest_purchase_dates.rename(columns={'PurchaseDate': 'LastPurchaseDate'}, inplace=True)
        df_products = pd.merge(df_products, latest_purchase_dates, on='ProductID', how='left')
        df_products.rename(columns={'LastPurchaseDate': 'PurchaseDate'}, inplace=True)
    else:
        df_products['PurchaseDate'] = pd.NaT

    required_cols = ['ProductID', 'ProductName', 'StockQuantity', 'ReorderPoint', 'Unit', 'Supplier', 'PurchaseDate', 'ExpiryDate', 'CostPricePerKg', 'SellingPricePerKg']
    for col in required_cols:
        if col not in df_products.columns:
            print(f"Warning: Required column '{col}' not found in df_products for reorder data. Returning empty.")
            return pd.DataFrame().to_dict('records')

    df_products['StockQuantity'] = pd.to_numeric(df_products['StockQuantity'], errors='coerce').fillna(0)
    df_products['ReorderPoint'] = pd.to_numeric(df_products['ReorderPoint'], errors='coerce').fillna(0)
    df_products['PurchaseDate'] = pd.to_datetime(df_products['PurchaseDate'], errors='coerce')
    df_products['ExpiryDate'] = pd.to_datetime(df_products['ExpiryDate'], errors='coerce')
    
    # --- Demand Forecasting and Trend Analysis (using sales data) ---
    demand_proxy = {} # Average daily sales over LONG_PERIOD_DAYS
    sales_analysis_flags = {} # To store HighDemand, UpwardTrend, ConsistentHighSales

    if not df_sales.empty and 'SaleDate' in df_sales.columns and 'Quantity' in df_sales.columns:
        df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
        df_sales['Quantity'] = pd.to_numeric(df_sales['Quantity'], errors='coerce').fillna(0)
        df_sales.dropna(subset=['SaleDate'], inplace=True) # Remove rows with invalid dates

        # Calculate average daily sales for various periods
        today = datetime.now().date()
        
        # Aggregate sales by ProductID and Date
        daily_sales = df_sales.groupby(['ProductID', df_sales['SaleDate'].dt.date])['Quantity'].sum().reset_index()
        daily_sales.rename(columns={'SaleDate': 'Date'}, inplace=True)

        for product_id in df_products['ProductID'].unique():
            product_sales = daily_sales[daily_sales['ProductID'] == product_id]
            
            # Initialize flags
            is_high_demand = False
            is_upward_trend = False
            is_consistent_high_sales = False

            # Sales over different periods
            sales_last_short_period = product_sales[product_sales['Date'] >= (today - timedelta(days=SHORT_PERIOD_DAYS))]['Quantity'].sum()
            sales_prev_short_period = product_sales[(product_sales['Date'] >= (today - timedelta(days=SHORT_PERIOD_DAYS * 2))) & (product_sales['Date'] < (today - timedelta(days=SHORT_PERIOD_DAYS)))]['Quantity'].sum()

            sales_last_long_period = product_sales[product_sales['Date'] >= (today - timedelta(days=LONG_PERIOD_DAYS))]['Quantity'].sum()
            sales_prev_long_period = product_sales[(product_sales['Date'] >= (today - timedelta(days=LONG_PERIOD_DAYS * 2))) & (product_sales['Date'] < (today - timedelta(days=LONG_PERIOD_DAYS)))]['Quantity'].sum()

            sales_very_long_period = product_sales[product_sales['Date'] >= (today - timedelta(days=VERY_LONG_PERIOD_DAYS))]['Quantity'].sum()

            avg_daily_sales_last_short = sales_last_short_period / SHORT_PERIOD_DAYS if SHORT_PERIOD_DAYS > 0 else 0
            avg_daily_sales_prev_short = sales_prev_short_period / SHORT_PERIOD_DAYS if SHORT_PERIOD_DAYS > 0 else 0
            avg_daily_sales_last_long = sales_last_long_period / LONG_PERIOD_DAYS if LONG_PERIOD_DAYS > 0 else 0
            avg_daily_sales_prev_long = sales_prev_long_period / LONG_PERIOD_DAYS if LONG_PERIOD_DAYS > 0 else 0
            avg_daily_sales_very_long = sales_very_long_period / VERY_LONG_PERIOD_DAYS if VERY_LONG_PERIOD_DAYS > 0 else 0


            demand_proxy[product_id] = avg_daily_sales_last_long # Use recent long period for demand proxy

            # Determine flags
            # High Demand / Sales Spike
            if avg_daily_sales_last_short > HIGH_VOLUME_THRESHOLD and avg_daily_sales_prev_short > 0 and avg_daily_sales_last_short >= avg_daily_sales_prev_short * SALES_SPIKE_FACTOR:
                 is_high_demand = True
            
            # Upward Trend (check for a sustained increase over longer periods)
            if not is_high_demand and avg_daily_sales_last_long > HIGH_VOLUME_THRESHOLD and avg_daily_sales_prev_long > 0 and avg_daily_sales_last_long >= avg_daily_sales_prev_long * UPWARD_TREND_FACTOR:
                is_upward_trend = True

            # Consistent High Sales Volume (check against a simple threshold)
            if not is_high_demand and not is_upward_trend and avg_daily_sales_very_long >= HIGH_VOLUME_THRESHOLD:
                is_consistent_high_sales = True
            
            sales_analysis_flags[product_id] = {
                'IsHighDemand': is_high_demand,
                'IsUpwardTrend': is_upward_trend,
                'IsConsistentHighSales': is_consistent_high_sales
            }
    else:
        print("Warning: Sales data is empty or missing required columns. Demand analysis skipped.")

    # --- Status Determination ---
    today = pd.to_datetime(datetime.now().date())
    df_products['STATUS_REORDER'] = 'Adequate'

    df_products.loc[(df_products['ExpiryDate'].notna()) & (df_products['ExpiryDate'] < today), 'STATUS_REORDER'] = 'Expired'
    df_products.loc[(df_products['ExpiryDate'].notna()) & (df_products['ExpiryDate'] >= today) &
                    (df_products['ExpiryDate'] <= today + timedelta(days=7)), 'STATUS_REORDER'] = 'Expiring Soon'
    df_products.loc[df_products['StockQuantity'] <= 0, 'STATUS_REORDER'] = 'Out of Stock'
    df_products.loc[(df_products['StockQuantity'] > 0) & 
                    (df_products['StockQuantity'] < df_products['ReorderPoint']), 'STATUS_REORDER'] = 'Low Stock'

    # Filter for reorder candidates based on STATUS_REORDER
    reorder_candidates = df_products[
        (df_products['STATUS_REORDER'] == 'Low Stock') |
        (df_products['STATUS_REORDER'] == 'Out of Stock') |
        (df_products['STATUS_REORDER'] == 'Expiring Soon') |
        (df_products['STATUS_REORDER'] == 'Expired')
    ].copy()

    # Add demand-driven products if they are not already reorder candidates by stock status
    demand_driven_products = []
    for index, row in df_products.iterrows():
        product_id = row['ProductID']
        flags = sales_analysis_flags.get(product_id, {})
        
        # Only consider adding if current status is 'Adequate' and a demand flag is true
        if row['STATUS_REORDER'] == 'Adequate' and (flags.get('IsHighDemand') or flags.get('IsUpwardTrend') or flags.get('IsConsistentHighSales')):
            # Temporarily calculate recommended qty to ensure it would be positive for these demand reasons
            temp_recommended_qty = calculate_reorder_qty_placeholder(
                row['ProductID'],
                row['StockQuantity'],
                row['ReorderPoint'],
                'Adequate', # Force 'Adequate' status for the temp calculation here
                demand_proxy,
                AVG_LEAD_TIME_DAYS,
                SAFETY_STOCK_BUFFER
            )
            if temp_recommended_qty > 0:
                demand_driven_products.append(row)
    
    df_demand_driven_products = pd.DataFrame(demand_driven_products)
    if not df_demand_driven_products.empty:
        # Concatenate and remove duplicates based on ProductID
        reorder_candidates = pd.concat([reorder_candidates, df_demand_driven_products]).drop_duplicates(subset=['ProductID']).copy()


    if reorder_candidates.empty:
        return pd.DataFrame().to_dict('records')

    # --- Reorder Quantity Calculation (AI/ML Placeholder) ---
    AVG_LEAD_TIME_DAYS = 7
    SAFETY_STOCK_BUFFER = 0.20 # 20% safety stock

    reorder_candidates['RECOMMENDED QTY'] = reorder_candidates.apply(
        lambda row: calculate_reorder_qty_placeholder(
            row['ProductID'],
            row['StockQuantity'],
            row['ReorderPoint'],
            row['STATUS_REORDER'], # Use actual status, could be 'Adequate' for new additions
            demand_proxy,
            AVG_LEAD_TIME_DAYS,
            SAFETY_STOCK_BUFFER
        ),
        axis=1
    ).round().astype(int)
    
    # Ensure recommended quantity is not negative
    reorder_candidates.loc[reorder_candidates['RECOMMENDED QTY'] < 0, 'RECOMMENDED QTY'] = 0

    # --- REVISED: Define functions to get display text and detailed text ---
    def get_reorder_reason_display(row): # This function returns the short, displayable reason
        # Core inventory management reasons (highest priority)
        if row['STATUS_REORDER'] == 'Out of Stock':
            return 'Critically Low Stock'
        elif row['STATUS_REORDER'] == 'Low Stock':
            return 'Below Reorder Point'
        elif row['STATUS_REORDER'] == 'Expiring Soon':
            return 'Expiring Soon'
        elif row['STATUS_REORDER'] == 'Expired':
            return 'Expired'
        
        # Demand-driven and Strategic Reasons (applied if not covered by core inventory reasons and RECOMMENDED QTY > 0)
        product_id = row['ProductID']
        flags = sales_analysis_flags.get(product_id, {})
        
        if row['RECOMMENDED QTY'] > 0: # Only assign these if a reorder is actually recommended
            if flags.get('IsHighDemand'):
                return 'High Demand / Sales Spike'
            elif flags.get('IsUpwardTrend'):
                return 'Upward Trend'
            elif flags.get('IsConsistentHighSales'):
                return 'Consistent High Sales Volume'
            else: # Fallback for other AI/ML reasons not specifically flagged (e.g., seasonality, promotions)
                return 'AI/ML Recommendation'
        
        return 'Adequate Stock' # Fallback, for items not needing reorder or having no flags

    def get_reorder_reason_detailed(row): # This function returns the FULL detailed text for the modal
        product_id = row['ProductID']
        flags = sales_analysis_flags.get(product_id, {})
        current_avg_daily_sales = demand_proxy.get(product_id, 0)
        demand_info = f"Current average daily sales: {current_avg_daily_sales:.2f} {row.get('Unit', 'units')}." if row.get('Unit') else f"Current average daily sales: {current_avg_daily_sales:.2f}."

        if row['STATUS_REORDER'] == 'Out of Stock':
            return 'Critically Low Stock (Urgent Restock): Stock quantity is zero or critically low, potentially nearing a stockout within a very short period (e.g., less than a few days\' supply). Requires immediate attention and often expedited ordering to prevent disruption in sales or operations.'
        elif row['STATUS_REORDER'] == 'Low Stock':
            return 'Below Reorder Point (System Triggered): Current stock has dropped to or below the pre-defined reorder point. This point is calculated to cover demand during the lead time plus a safety stock, ensuring a continuous supply under normal conditions.'
        elif row['STATUS_REORDER'] == 'Expiring Soon':
            return 'Expiring Soon (Waste Mitigation): Product has an upcoming expiry date (e.g., within 30 days). Reordering is recommended to ensure fresh stock is available, while also prompting actions to sell or move existing expiring stock to minimize waste.'
        elif row['STATUS_REORDER'] == 'Expired':
            return 'Expired (Waste Mitigation): The product\'s shelf life has ended. These items are typically marked for disposal. A reorder recommendation here implies replacement of truly expired stock that has been removed from inventory.'
        elif flags.get('IsHighDemand'):
            return f"High Demand / Sales Spike (Market Responsiveness): Current sales volumes are significantly higher than the historical average or forecast ({demand_info}), indicating an unexpected surge in customer demand. Could be due to unexpected market trends, competitor issues, sudden popularity, or effective marketing campaigns. Requires immediate reordering to capitalize on the opportunity and avoid lost sales. Lead time: {AVG_LEAD_TIME_DAYS} days, Safety stock buffer: {SAFETY_STOCK_BUFFER*100}%."
        elif flags.get('IsUpwardTrend'):
            return f"Upward Trend (Growth & Anticipation): Analysis of sales data over a longer period reveals a consistent increase in sales volume ({demand_info}). This is a sustained growth pattern rather than a sudden spike. Suggests a growing market share or increasing popularity. Reordering proactively ensures you meet future demand, prevent stockouts, and maintain customer satisfaction as the product gains traction. Lead time: {AVG_LEAD_TIME_DAYS} days, Safety stock buffer: {SAFETY_STOCK_BUFFER*100}%."
        elif flags.get('IsConsistentHighSales'):
            return f"Consistent High Sales Volume (Stable Performance): The product consistently sells at a high volume ({demand_info}) over multiple periods, indicating it's a popular or staple item with reliable demand. These are 'cash cow' products. Reordering ensures you always have adequate stock to support ongoing, predictable high sales without interruption, optimizing inventory turnover. Lead time: {AVG_LEAD_TIME_DAYS} days, Safety stock buffer: {SAFETY_STOCK_BUFFER*100}%."
        elif row['RECOMMENDED QTY'] > 0: # General AI/ML if not specifically categorized above but still recommended
             return (
                 f"AI/ML Recommendation (Predictive Optimization): This recommendation is generated by advanced algorithms considering multiple complex factors beyond simple thresholds. "
                 f"These could include: seasonality, promotional impact, supplier lead time fluctuations, economic indicators, or market basket analysis. "
                 f"Based on these predictive insights, the system anticipates future demand. This recommendation helps in capitalizing on opportunities and preventing potential stockouts. "
                 f"Assumptions: Average lead time of {AVG_LEAD_TIME_DAYS} days and a safety stock buffer: {SAFETY_STOCK_BUFFER*100}%."
             )
        return 'Adequate Stock: Current stock levels are sufficient and do not require immediate reordering.'


    reorder_candidates['REASON FOR REORDER'] = reorder_candidates.apply(get_reorder_reason_display, axis=1)
    reorder_candidates['REASON_FOR_REORDER_DETAIL_HIDDEN'] = reorder_candidates.apply(get_reorder_reason_detailed, axis=1)
    
    reorder_candidates['ADJUST QUANTITY'] = reorder_candidates['RECOMMENDED QTY']
    reorder_candidates['CYCLIC REORDER'] = 'N/A'

    final_cols_for_table = [
        "ProductName", "Supplier", "StockQuantity", "PurchaseDate",
        "REASON FOR REORDER", "RECOMMENDED QTY", "ADJUST QUANTITY", "CYCLIC REORDER",
        "REASON_FOR_REORDER_DETAIL_HIDDEN"
    ]

    df_for_table = reorder_candidates[final_cols_for_table].rename(columns={
        "ProductName": "PRODUCT",
        "StockQuantity": "CURRENT STOCK",
        "PurchaseDate": "LAST REORDER DATE",
        "Supplier": "SUPPLIER"
    })

    if 'LAST REORDER DATE' in df_for_table.columns and pd.api.types.is_datetime64_any_dtype(df_for_table['LAST REORDER DATE']):
        df_for_table['LAST REORDER DATE'] = df_for_table['LAST REORDER DATE'].dt.strftime('%Y-%m-%d')
    else:
        df_for_table['LAST REORDER DATE'] = df_for_table['LAST REORDER DATE'].astype(str)

    return df_for_table.to_dict('records')

# --- REVISED: Callback to open/close modal and populate content ---
@app.callback(
    Output('modal', 'is_open'),
    Output('modal-body', 'children'),
    Input('reorder-recommendations-table', 'active_cell'),
    Input('close-modal', 'n_clicks'),
    State('reorder-recommendations-table', 'data'),
    State('modal', 'is_open'),
    prevent_initial_call=True # Prevent callback from firing on initial load if no active_cell or n_clicks
)
def display_modal(active_cell, n_clicks_close, data, is_open):
    ctx = dash.callback_context

    if not ctx.triggered:
        return is_open, dash.no_update

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'close-modal' and n_clicks_close:
        return False, dash.no_update # Close modal on close button click

    if trigger_id == 'reorder-recommendations-table' and active_cell:
        # Check if the clicked cell is in the 'REASON FOR REORDER' column
        # AND its displayed value is NOT 'Adequate Stock' (i.e., it's a reorder reason)
        if active_cell['column_id'] == 'REASON FOR REORDER' and \
           data[active_cell['row']].get('REASON FOR REORDER') != 'Adequate Stock':

            row_id = active_cell['row']
            row_data = data[row_id]

            # Get the detailed reason from the HIDDEN column
            detailed_reason = row_data.get('REASON_FOR_REORDER_DETAIL_HIDDEN', 'No detailed reason available.')

            # Construct detailed message for the modal
            modal_content = [
                html.P(f"Product: {row_data.get('PRODUCT', 'N/A')}"),
                html.P(f"Current Stock: {row_data.get('CURRENT STOCK', 'N/A')}"),
                html.P(f"Last Reorder Date: {row_data.get('LAST REORDER DATE', 'N/A')}"),
                html.P(f"Supplier: {row_data.get('SUPPLIER', 'N/A')}"),
                html.P(f"Recommended Quantity: {row_data.get('RECOMMENDED QTY', 'N/A')}"),
                html.P(f"Adjust Quantity: {row_data.get('ADJUST QUANTITY', 'N/A')}"),
                html.P(f"Cyclic Reorder: {row_data.get('CYCLIC REORDER', 'N/A')}"),
                html.Hr(), # Separator
                html.H6("Reorder Reason Details:"),
                html.P(detailed_reason) # Use the detailed reason from the hidden column
            ]
            return True, modal_content # Open modal and populate
    
    # If no relevant trigger or condition met, keep modal state as is
    return is_open, dash.no_update

# --- 1. Dummy Data Definitions ---
# This data will be used to populate the tables for visual testing.
# REMEMBER: You will need to replace this with logic that processes your real CSV data later.

# Dummy Data for the TOP Summary Table (corrected 'Actions' column)
dummy_summary_table_data = [
    {
        "Supplier Name": "Global Foods Inc.",
        "Past Deliveries": "Avg 2 Days", # Updated as per request
        "Phone No": "555-111-2222",
        "Lead Time Variability": "Low", # Updated as per request
        "Order Fulfillment (%)": "98.5%",
        "Average Rating": 4.8,
        "Actions": "View"
    },
    {
        "Supplier Name": "Produce Pro Co.",
        "Past Deliveries": "Avg 1.5 Days", # Updated as per request
        "Phone No": "555-333-4444",
        "Lead Time Variability": "Very Low", # Updated as per request
        "Order Fulfillment (%)": "99.1%",
        "Average Rating": 4.9,
        "Actions": "View"
    },
    {
        "Supplier Name": "Bakery Delights Ltd.",
        "Past Deliveries": "Avg 3 Days", # Updated as per request
        "Phone No": "555-555-6666",
        "Lead Time Variability": "Medium", # Updated as per request
        "Order Fulfillment (%)": "97.0%",
        "Average Rating": 4.5,
        "Actions": "View"
    },
    {
        "Supplier Name": "Meat Masters LLC",
        "Past Deliveries": "Avg 4 Days", # Updated as per request
        "Phone No": "555-777-8888",
        "Lead Time Variability": "High", # Updated as per request
        "Order Fulfillment (%)": "95.2%",
        "Average Rating": 4.2,
        "Actions": "View"
    },
    {
        "Supplier Name": "Beverage Best Corp.",
        "Past Deliveries": "Avg 2.5 Days", # Updated as per request
        "Phone No": "555-999-0000",
        "Lead Time Variability": "Medium", # Updated as per request
        "Order Fulfillment (%)": "98.0%",
        "Average Rating": 4.7,
        "Actions": "View"
    }
]

# Define columns for the TOP Summary DataTable (no change needed here as names are already strings)
summary_table_columns = [
    {"name": "Supplier Name", "id": "Supplier Name"},
    {"name": "Past Deliveries", "id": "Past Deliveries"},
    {"name": "Phone No", "id": "Phone No"},
    {"name": "Lead Time Variability", "id": "Lead Time Variability"},
    {"name": "Order Fulfillment (%)", "id": "Order Fulfillment (%)"},
    {"name": "Average Rating", "id": "Average Rating"},
    {"name": "Actions", "id": "Actions", "presentation": "markdown"}
]

# NEW: Dummy Products List
dummy_products = ["Bread", "Milk", "Eggs", "Cheese", "Meat", "Beverages"]

# NEW: Granular Dummy Data for Supplier Performance per Product
dummy_product_supplier_metrics = {
    "Global Foods Inc.": {
        "Bread": {
            "Past Deliveries": "Avg 2 Days",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "Low",
            "Order Fulfillment (%)": "98.5%",
            "Average Rating": 4.8,
            "Quality Score": "9.0/10",
            "Price per unit": 40
        },
        "Milk": {
            "Past Deliveries": "Avg 1 Day",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "Very Low",
            "Order Fulfillment (%)": "99.0%",
            "Average Rating": 4.9,
            "Quality Score": "9.5/10",
            "Price per unit": 60
        },
        "Eggs": {
            "Past Deliveries": "Avg 2 Days",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "Low",
            "Order Fulfillment (%)": "98.0%",
            "Average Rating": 4.7,
            "Quality Score": "8.8/10",
            "Price per unit": 120
        },
        "Cheese": {
            "Past Deliveries": "Avg 3 Days",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "Medium",
            "Order Fulfillment (%)": "97.5%",
            "Average Rating": 4.6,
            "Quality Score": "8.5/10",
            "Price per unit": 350
        },
        "Meat": {
            "Past Deliveries": "Avg 4 Days",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "High",
            "Order Fulfillment (%)": "95.0%",
            "Average Rating": 4.2,
            "Quality Score": "8.0/10",
            "Price per unit": 250
        },
        "Beverages": {
            "Past Deliveries": "Avg 2.5 Days",
            "Phone No": "555-111-2222",
            "Lead Time Variability": "Medium",
            "Order Fulfillment (%)": "98.0%",
            "Average Rating": 4.7,
            "Quality Score": "9.1/10",
            "Price per unit": 100
        }
    },
    "Produce Pro Co.": {
        "Bread": {
            "Past Deliveries": "Avg 1.5 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Very Low",
            "Order Fulfillment (%)": "99.1%",
            "Average Rating": 4.9,
            "Quality Score": "9.5/10",
            "Price per unit": 45
        },
        "Milk": {
            "Past Deliveries": "Avg 2 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Low",
            "Order Fulfillment (%)": "98.5%",
            "Average Rating": 4.8,
            "Quality Score": "9.2/10",
            "Price per unit": 65
        },
        "Eggs": {
            "Past Deliveries": "Avg 1.8 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Very Low",
            "Order Fulfillment (%)": "99.5%",
            "Average Rating": 5.0,
            "Quality Score": "9.8/10",
            "Price per unit": 115
        },
        "Cheese": {
            "Past Deliveries": "Avg 2.5 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Low",
            "Order Fulfillment (%)": "98.0%",
            "Average Rating": 4.7,
            "Quality Score": "9.0/10",
            "Price per unit": 340
        },
        "Meat": {
            "Past Deliveries": "Avg 3.5 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Medium",
            "Order Fulfillment (%)": "96.0%",
            "Average Rating": 4.4,
            "Quality Score": "8.5/10",
            "Price per unit": 260
        },
        "Beverages": {
            "Past Deliveries": "Avg 2 Days",
            "Phone No": "555-333-4444",
            "Lead Time Variability": "Low",
            "Order Fulfillment (%)": "98.5%",
            "Average Rating": 4.8,
            "Quality Score": "9.3/10",
            "Price per unit": 95
        }
    },
    "Bakery Delights Ltd.": { # Add more product data for this supplier if needed
         "Bread": {
            "Past Deliveries": "Avg 2 Days",
            "Phone No": "555-555-6666",
            "Lead Time Variability": "Medium",
            "Order Fulfillment (%)": "97.0%",
            "Average Rating": 4.5,
            "Quality Score": "8.7/10",
            "Price per unit": 38
        }
    }
}


# --- 2. Supplier Management Layout ---
supplier_management_layout = html.Div(
    [
        # Page Header
        html.Div(
            [
                html.H2("Supplier Management", className="display-4 mb-0"),
                html.P("Monitor supplier performance and details.", className="lead text-muted"),
            ],
            className="d-flex justify-content-between align-items-center mb-4"
        ),

        # TOP SECTION: Summary Table
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Supplier Performance Overview", className="card-title"),
dash_table.DataTable(
    id='supplier-summary-data-table',
    columns=summary_table_columns,
    data=dummy_summary_table_data,

    style_table={'overflowX': 'auto', 'minWidth': '100%'},
    style_header={
        'backgroundColor': 'rgb(230, 230, 230)',
        'fontWeight': 'bold',
        'textAlign': 'left',
        'padding': '10px 15px',
        'borderBottom': '1px solid #ddd',
    },
    style_data={
        'backgroundColor': 'white',
        'textAlign': 'left',
        'padding': '10px 15px',
        'borderBottom': '1px solid #eee',
    },
    style_cell={'fontFamily': 'Inter, sans-serif', 'fontSize': '0.9rem'},
    page_action='none',

    style_cell_conditional=[
        {
            'if': {'column_id': 'Actions'},
            'textAlign': 'center',
            'width': '80px',
            'minWidth': '80px',
            'maxWidth': '80px',
        }
    ],
    
)
                ],
            ),
            className="mb-4 shadow-sm h-100"
        ),

        # MIDDLE SECTION: Supplier Comparison Table (now with Product Dropdown)
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Supplier Performance Comparison", className="card-title"),
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Dropdown(
                                    id='supplier-comparison-dropdown-1',
                                    options=[{'label': s['Supplier Name'], 'value': s['Supplier Name']} for s in dummy_summary_table_data],
                                    value='Global Foods Inc.', # Default selection
                                    placeholder="Select Supplier 1",
                                    clearable=False, # Ensure a supplier is always selected
                                    className="mb-3"
                                ),
                                md=4
                            ),
                            dbc.Col(
                                dcc.Dropdown(
                                    id='supplier-comparison-dropdown-2',
                                    options=[{'label': s['Supplier Name'], 'value': s['Supplier Name']} for s in dummy_summary_table_data],
                                    value='Produce Pro Co.', # Default selection
                                    placeholder="Select Supplier 2",
                                    clearable=False, # Ensure a supplier is always selected
                                    className="mb-3"
                                ),
                                md=4
                            ),
                            dbc.Col(
                                dcc.Dropdown(
                                    id='product-comparison-dropdown', # NEW Product Dropdown
                                    options=[{'label': p, 'value': p} for p in dummy_products],
                                    value='Bread', # Default selected product
                                    placeholder="Select Product",
                                    clearable=False, # Ensure a product is always selected
                                    className="mb-3"
                                ),
                                md=4
                            ),
                        ],
                        className="mb-3"
                    ),
                    dash_table.DataTable(
    id='supplier-comparison-table',
    columns=[], # Columns will be set by callback
    data=[],    # Data will be set by callback

    style_table={'overflowX': 'auto', 'minWidth': '100%'},
    style_header={
        'backgroundColor': 'rgb(230, 230, 230)',
        'fontWeight': 'bold',
        'textAlign': 'left',
        'padding': '10px 15px',
        'borderBottom': '1px solid #ddd',
    },
    style_data={
        'backgroundColor': 'white',
        'textAlign': 'left',
        'padding': '10px 15px',
        'borderBottom': '1px solid #eee',
    },
    style_cell={'fontFamily': 'Inter, sans-serif', 'fontSize': '0.9rem'},
    # ADD THIS NEW SECTION for conditional styling
    
    style_data_conditional=[
        # Lead Time Variability
        {
            'if': {'column_id': 'Lead Time Variability', 'filter_query': '{Lead Time Variability} eq "Very Low"'},
            'style': {
                'backgroundColor': '#d4edda', # Light green
                'color': '#155724',           # Dark green text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Lead Time Variability', 'filter_query': '{Lead Time Variability} eq "Low"'},
            'style': {
                'backgroundColor': '#d4edda', # Light green
                'color': '#155724',           # Dark green text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Lead Time Variability', 'filter_query': '{Lead Time Variability} eq "Medium"'},
            'style': {
                'backgroundColor': '#fff3cd', # Light yellow/orange
                'color': '#856404',           # Dark yellow/orange text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Lead Time Variability', 'filter_query': '{Lead Time Variability} eq "High"'},
            'style': {
                'backgroundColor': '#f8d7da', # Light red
                'color': '#721c24',           # Dark red text
                'fontWeight': '500'
            }
        },
        # Order Fulfillment (%) - Based on string content. Adjust ranges as needed.
        {
            'if': {'column_id': 'Order Fulfillment (%)', 'filter_query': '{Order Fulfillment (%)} contains "99." || {Order Fulfillment (%)} contains "100."'},
            'style': {
                'backgroundColor': '#d4edda', # Light green
                'color': '#155724',           # Dark green text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Order Fulfillment (%)', 'filter_query': '{Order Fulfillment (%)} contains "98."'},
            'style': {
                'backgroundColor': '#e2f2e5', # Slightly lighter green
                'color': '#28a745',           # Green text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Order Fulfillment (%)', 'filter_query': '{Order Fulfillment (%)} contains "97."'},
            'style': {
                'backgroundColor': '#fff3cd', # Light yellow/orange
                'color': '#856404',           # Dark yellow/orange text
                'fontWeight': '500'
            }
        },
        {
            'if': {'column_id': 'Order Fulfillment (%)', 'filter_query': '{Order Fulfillment (%)} contains "96." || {Order Fulfillment (%)} contains "95." || {Order Fulfillment (%)} contains "94."'},
            'style': {
                'backgroundColor': '#f8d7da', # Light red
                'color': '#721c24',           # Dark red text
                'fontWeight': '500'
            }
        },
    ]
)
                ]
            ),
            className="mb-4 shadow-sm h-100"
        ),
    ],
    className="content"
)


# --- 3. Callbacks for Supplier Management Page ---

# Callback for the TOP Summary Table
@app.callback(
    Output('supplier-summary-data-table', 'data'),
    [Input('url', 'pathname')]
)
def get_dummy_supplier_summary_data(pathname):
    return dummy_summary_table_data

# NEW/UPDATED Callback for the Supplier Comparison Table (now product-specific)
@app.callback(
    Output('supplier-comparison-table', 'data'),
    Output('supplier-comparison-table', 'columns'), # Output for dynamic columns
    [Input('supplier-comparison-dropdown-1', 'value'),
     Input('supplier-comparison-dropdown-2', 'value'),
     Input('product-comparison-dropdown', 'value')] # NEW Input: selected product
)
def update_supplier_comparison_table(supplier1_name, supplier2_name, selected_product):
    # Initialize comparison data and columns
    comparison_data = []
    comparison_columns = [
        {"name": "Metric", "id": "Metric"},
        {"name": supplier1_name, "id": "Supplier 1"},
        {"name": supplier2_name, "id": "Supplier 2"},
    ]

    # Get metrics for selected product and suppliers
    metrics_s1 = dummy_product_supplier_metrics.get(supplier1_name, {}).get(selected_product, {})
    metrics_s2 = dummy_product_supplier_metrics.get(supplier2_name, {}).get(selected_product, {})

    # Define the order and names of the metrics for the comparison table
    metric_keys = [
        "Past Deliveries",
        "Phone No",
        "Lead Time Variability",
        "Order Fulfillment (%)",
        "Average Rating",
        "Quality Score",
        "Price per unit" # This will be special-cased
    ]

    for key in metric_keys:
        value_s1 = metrics_s1.get(key, "N/A")
        value_s2 = metrics_s2.get(key, "N/A")

        row = {"Metric": key}

        # Special handling for "Price per unit"
        if key == "Price per unit":
            row["Metric"] = f"Price per unit of {selected_product}"
            # Format as Indian Rupees
            row["Supplier 1"] = f"₹{value_s1}" if value_s1 != "N/A" else "N/A"
            row["Supplier 2"] = f"₹{value_s2}" if value_s2 != "N/A" else "N/A"
        else:
            row["Supplier 1"] = str(value_s1)
            row["Supplier 2"] = str(value_s2)
        
        comparison_data.append(row)
        
    return comparison_data, comparison_columns


# --- Dummy Data for Sales & Trends Page ---
# This will be used for the carousel and initial chart placeholders.
# REMEMBER: You will replace chart data with logic processing your real CSV data later.

# Dummy data for the Carousel
dummy_carousel_items = [
    {
        "key": "1",
        "src": "/assets/monsoon_raincoat_sales.png", # Placeholder: Chart showing increase in raincoat sales
        "header": "Monsoon Season Surge: Zeel Raincoat Dominance",
        "caption": "Significant spike in Zeel Raincoat sales across all regions, driven by early and heavy monsoon showers.",
        "img_alt": "Line chart showing a sharp increase in Zeel Raincoat sales during monsoon months."
    },
    {
        "key": "2",
        "src": "/assets/health_home_comfort_sales.png", # Placeholder: Chart showing sales of dehumidifiers/air purifiers
        "header": "Health & Home Comfort: Humidity Solutions",
        "caption": "Increased demand for dehumidifiers and air purifiers as consumers combat monsoon humidity and associated indoor air quality concerns.",
        "img_alt": "Bar chart illustrating higher sales of home comfort appliances like dehumidifiers and air purifiers."
    },
    {
        "key": "3", # This is the changed item
        "src": "/assets/warm_beverages_comfort_food_sales.png", # Placeholder: Chart showing sales of specific F&B items
        "header": "Warm Beverages & Comfort Food Craze",
        "caption": "Surge in sales of tea, coffee, instant noodles, and baking essentials, reflecting consumer preference for warm and convenient options during monsoon.",
        "img_alt": "Chart depicting increased sales of hot beverages and convenience foods."
    }
]

# Dummy Data for Chart Placeholders (You'll replace this with your CSV data)
# For demonstration purposes, creating a simple DataFrame.
# In a real scenario, you'd load from your sales/product CSVs.
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Dummy data for daily sales over 6 months
end_date = datetime.now()
start_date = end_date - timedelta(days=180)
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

dummy_sales_chart_data = pd.DataFrame({
    'Date': date_range,
    'Total Sales': np.random.randint(5000, 25000, len(date_range)),
    'Units Sold': np.random.randint(100, 500, len(date_range)),
    'Product Category': np.random.choice(['Electronics', 'Dairy', 'Produce', 'Bakery', 'Beverages', 'Meat'], len(date_range)),
    'Region': np.random.choice(['North', 'South', 'East', 'West'], len(date_range))
})

# --- 3. Sales and Trends Reports Layout ---
sales_trends_layout = html.Div(
    [
        # Page Header
        html.Div(
            [
                html.H2("Sales & Trends Reports", className="display-4 mb-0"),
                html.P("Analyze sales performance and identify market trends.", className="lead text-muted"),
            ],
            className="d-flex justify-content-between align-items-center mb-4"
        ),

        # TOP SECTION: Key Trends (Manual Carousel)
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Key Sales Trends", className="card-title mb-3"),
                    dcc.Store(id='current-carousel-index', data=0), # Store to keep track of current slide index

                    html.Div(id='manual-carousel-content', className="text-center mb-3", style={'min-height': '350px'}), # Container for the active slide

                    dbc.Row(
                        [
                            dbc.Col(dbc.Button("Previous", id="prev-carousel-btn", color="primary", className="me-2"), width="auto"),
                            dbc.Col(dbc.Button("Next", id="next-carousel-btn", color="primary", className="ms-2"), width="auto"),
                        ],
                        justify="center",
                        className="mt-3"
                    )
                ]
            ),
            className="mb-4 shadow-sm h-100",
            id="sales-trends-main-content" # Keep this ID for CSS targeting
        ),

        # MIDDLE SECTION: Sales and Profit Overview Charts (Row 1)
# --- Updated Sales & Profit Cards (Layout) ---
dbc.Row([
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div([
                    html.Div("Sales Data", className="fs-5 fw-bold text-success"),
                    # --- NEW: Date Picker ---
                    dcc.DatePickerSingle(
                        id='sales-trend-date-picker',
                        min_date_allowed=datetime(2020, 1, 1),
                        max_date_allowed=datetime.now(),
                        initial_visible_month=datetime.now(),
                        date=datetime.now().date(), # Default to today
                        display_format='DD/MM/YYYY',
                        className="mb-2 ms-auto" # Push to right if flex, or margin bottom
                    )
                ], className="d-flex justify-content-between align-items-center mb-2"),

                # Aggregation Buttons
                html.Div([
                    dbc.Button("Daily", id="sales-agg-daily", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Weekly", id="sales-agg-weekly", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Monthly", id="sales-agg-monthly", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Yearly", id="sales-agg-yearly", className="btn-sm", n_clicks=0),
                ], className="mb-3"),

                # KPI Display
                html.Div([
                    html.H3(id='sales-total-kpi', className="display-5 fw-bold text-primary mb-0"),
                    html.Small(id='sales-change-kpi', className="text-success")
                ], className="d-flex flex-column align-items-start mb-3"),

                dcc.Graph(id='total-sales-over-time-chart', figure={})
            ]), className="h-100"
        ), md=6
    ),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div("Profit Data", className="mb-4 fs-5 fw-bold text-success"), # Spacer to align with Sales card
                
                # We reuse the buttons/picker from the Sales card to control both, 
                # or you can duplicate them here if you want independent control. 
                # For this UI, the left controls typically drive both for comparison.
                html.Div([
                    dbc.Button("Daily", id="profit-agg-daily", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Weekly", id="profit-agg-weekly", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Monthly", id="profit-agg-monthly", className="me-1 btn-sm", n_clicks=0),
                    dbc.Button("Yearly", id="profit-agg-yearly", className="btn-sm", n_clicks=0),
                ], className="mb-3"),

                html.Div([
                    html.H3(id='profit-total-kpi', className="display-5 fw-bold text-success mb-0"),
                    html.Small(id='profit-change-kpi', className="text-success")
                ], className="d-flex flex-column align-items-start mb-3"),

                dcc.Graph(id='total-profit-over-time-chart', figure={})
            ]), className="h-100"
        ), md=6
    ),
], className="mb-4"),

# --- NEW: Product Seasonal Trends Card/Section ---
dbc.Card(
    dbc.CardBody([
        html.Div([
            html.H5("Product Seasonal Trends", className="card-title mb-3"),
            dbc.Row([
                dbc.Col(dcc.Dropdown(
                    id='product-seasonal-dropdown',
                    options=[
                        # Options will be populated by a callback from your product list
                        # Example: {'label': 'Winter Coats', 'value': 'Winter Coats'},
                        #          {'label': 'Summer Dresses', 'value': 'Summer Dresses'}
                    ],
                    placeholder="Select Product",
                    className="mb-3",
                    value=None
                ), width=6),
                dbc.Col(dcc.Dropdown(
                    id='seasonal-year-dropdown',
                    options=[
                        {'label': 'This Year (Projected)', 'value': 'current_projected'},
                        # Add options for historical years if available in your data
                        # {'label': '2024', 'value': '2024'},
                        # {'label': '2023', 'value': '2023'},
                    ],
                    value='current_projected', # Default selection
                    clearable=False,
                    className="mb-3"
                ), width=6),
            ]),
            html.Div(id='product-seasonal-kpi', className="text-center mb-3"), # KPI display area
            dcc.Graph(id='product-seasonal-chart', config={'displayModeBar': False})
        ])
    ]),
    className="mb-4" # Add some bottom margin to the card
),
# --- END NEW ---

# Add this after the 'Product Seasonal Trends' section, or wherever you want it to appear.
dbc.Col(lg=12, children=[ # Adjust lg/md/sm as per your layout needs
    dbc.Card(className="card-container", children=[
        dbc.CardBody([
            html.Div(className="d-flex justify-content-between align-items-center", children=[
                html.H4("Product & Brand Sales Chart", className="card-title"),
                html.Div([
                    dcc.Dropdown(
                        id='product-brand-product-dropdown',
                        options=[], # Options will be set by callback
                        value=None, # Default value
                        placeholder="Select Product",
                        clearable=False,
                        style={'width': '200px', 'marginRight': '10px'} # Adjust styling
                    ),
                    
                     # --- NEW: Year Dropdown ---
                    dcc.Dropdown(
                        id='product-brand-year-dropdown',
                        options=[], # Populated by callback
                        value=None, # Default value, e.g., 2025 or max year
                        placeholder="Select Year",
                        clearable=True, # Allow clearing to see all years
                        style={'width': '120px', 'marginRight': '10px'}
                    ),

                    # --- NEW: Quarter Dropdown ---
                    dcc.Dropdown(
                        id='product-brand-quarter-dropdown',
                        options=[ # Static options for quarters
                            {'label': 'Q1', 'value': 1},
                            {'label': 'Q2', 'value': 2},
                            {'label': 'Q3', 'value': 3},
                            {'label': 'Q4', 'value': 4},
                        ],
                        value=None,
                        placeholder="Select Quarter",
                        clearable=True, # Allow clearing
                        style={'width': '120px', 'marginRight': '10px'}
                    ),

                    # --- NEW: Month Dropdown ---
                    dcc.Dropdown(
                        id='product-brand-month-dropdown',
                        options=[ # Static options for months
                            {'label': 'January', 'value': 1},
                            {'label': 'February', 'value': 2},
                            {'label': 'March', 'value': 3},
                            {'label': 'April', 'value': 4},
                            {'label': 'May', 'value': 5},
                            {'label': 'June', 'value': 6},
                            {'label': 'July', 'value': 7},
                            {'label': 'August', 'value': 8},
                            {'label': 'September', 'value': 9},
                            {'label': 'October', 'value': 10},
                            {'label': 'November', 'value': 11},
                            {'label': 'December', 'value': 12},
                        ],
                        value=None,
                        placeholder="Select Month",
                        clearable=True, # Allow clearing
                        style={'width': '120px', 'marginRight': '10px'}
                    ),

                    
                    # Hidden Div to store the active time aggregation for brand sales
                    dcc.Store(id='brand-sales-time-agg-state', data='Monthly'), # Default to Monthly
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ]),
            dcc.Graph(id='product-brand-sales-chart', className="mt-3")
        ])
    ])
]),
 ],
className="content-container p-4",# Use your existing content-container class for padding
id="sales-trends-main-content"
)


# --- Manual Carousel Callback ---
# Assuming dummy_carousel_items is defined correctly at the top of your app.py

# Callback to update the manual carousel content and index
@app.callback(
    Output('manual-carousel-content', 'children'),
    Output('current-carousel-index', 'data'),
    Input('prev-carousel-btn', 'n_clicks'),
    Input('next-carousel-btn', 'n_clicks'),
    State('current-carousel-index', 'data'),
    prevent_initial_call=True
)
def update_manual_carousel(n_clicks_prev, n_clicks_next, current_index):
    ctx = dash.callback_context

    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    num_items = len(dummy_carousel_items)

    new_index = current_index
    if button_id == 'next-carousel-btn':
        new_index = (current_index + 1) % num_items
    elif button_id == 'prev-carousel-btn':
        new_index = (current_index - 1 + num_items) % num_items
    # No 'else' needed here, as prevent_initial_call handles initial state

    # Create the content for the current slide
    item = dummy_carousel_items[new_index]
    carousel_slide_content = html.Div(
        [
            # Image Container: Use a div to control image dimensions and centering
            html.Div(
                html.Img(
                    src=item["src"],
                    alt=item["img_alt"],
                    className="manual-carousel-image" # Apply custom CSS class here
                ),
                className="manual-carousel-image-container" # Apply custom CSS class here
            ),
            html.H5(item["header"], className="manual-carousel-header"), # Use custom class for H5
            html.P(item["caption"], className="manual-carousel-caption") # Use custom class for P
        ],
        className="d-flex flex-column align-items-center justify-content-center manual-carousel-slide", # Add custom class for slide
        style={'height': '100%'} # Ensure inner div takes full height of parent container
    )

    return carousel_slide_content, new_index

# Callback to display the first item on initial load
@app.callback(
    Output('manual-carousel-content', 'children', allow_duplicate=True),
    Input('current-carousel-index', 'data'), # This input will be triggered by initial data=0
    prevent_initial_call='initial_duplicate'
)
def display_initial_carousel_item(current_index):
    if current_index is None:
        current_index = 0 # Fallback, though data=0 should ensure it's not None

    item = dummy_carousel_items[current_index]
    carousel_slide_content = html.Div(
        [
            html.Div(
                html.Img(
                    src=item["src"],
                    alt=item["img_alt"],
                    className="manual-carousel-image"
                ),
                className="manual-carousel-image-container"
            ),
            html.H5(item["header"], className="manual-carousel-header"),
            html.P(item["caption"], className="manual-carousel-caption")
        ],
        className="d-flex flex-column align-items-center justify-content-center manual-carousel-slide",
        style={'height': '100%'}
    )
    return carousel_slide_content

# Helper function to aggregate data based on time period and specified column names
# --- Updated Data Aggregation Logic (Filtering) ---
def aggregate_data(df, time_agg, date_col, value_col):
    if df.empty:
        return pd.DataFrame(columns=['Date', value_col])

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df.dropna(subset=[date_col], inplace=True)

    today = pd.to_datetime(datetime.now().date())
    agg_df = pd.DataFrame()

    if time_agg == 'Daily':
        # Filter: Current Date Only
        # Note: If your CSV only has dates (no times), this will return a single point. 
        # If it has times, it will show the trend throughout the day.
        agg_df = df[df[date_col].dt.date == today.date()].copy()
        # If we have time data, we could group by hour here. 
        # For now, we assume simple date-based rows.
        agg_df = agg_df.groupby(date_col)[value_col].sum().reset_index()

    elif time_agg == 'Weekly':
        # Filter: Last 7 Days (Current Week view)
        start_date = today - timedelta(days=6) # Today + 6 previous days
        filtered_df = df[(df[date_col] >= start_date) & (df[date_col] <= today)].copy()
        agg_df = filtered_df.groupby(date_col)[value_col].sum().reset_index()

    elif time_agg == 'Monthly':
        # Filter: Current Month Only (1st to Today)
        filtered_df = df[(df[date_col].dt.month == today.month) & (df[date_col].dt.year == today.year)].copy()
        agg_df = filtered_df.groupby(date_col)[value_col].sum().reset_index()

    elif time_agg == 'Yearly':
        # Filter: Current Year Only
        filtered_df = df[df[date_col].dt.year == today.year].copy()
        # Group by Month for the Yearly view
        filtered_df['MonthPeriod'] = filtered_df[date_col].dt.to_period('M').dt.to_timestamp()
        agg_df = filtered_df.groupby('MonthPeriod')[value_col].sum().reset_index()
        agg_df.rename(columns={'MonthPeriod': 'Date'}, inplace=True)

    # Ensure column naming consistency
    if 'Date' not in agg_df.columns and date_col in agg_df.columns:
        agg_df.rename(columns={date_col: 'Date'}, inplace=True)
        
    return agg_df


# --- Callback to update Sales Time Aggregation State ---
@app.callback(
    Output('sales-time-agg-state', 'data'),
    Input('sales-agg-daily', 'n_clicks'),
    Input('sales-agg-weekly', 'n_clicks'),
    Input('sales-agg-monthly', 'n_clicks'),
    Input('sales-agg-yearly', 'n_clicks'),
    State('sales-time-agg-state', 'data')
)
def update_sales_agg_state(d, w, m, y, current_state):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_state
    button_id = ctx.triggered [0]['prop_id'].split('.')[0]
    if button_id == 'sales-agg-daily': return 'Daily'
    elif button_id == 'sales-agg-weekly': return 'Weekly'
    elif button_id == 'sales-agg-monthly': return 'Monthly'
    elif button_id == 'sales-agg-yearly': return 'Yearly'
    return current_state

# --- Callback to update Profit Time Aggregation State ---
@app.callback(
    Output('profit-time-agg-state', 'data'),
    Input('profit-agg-daily', 'n_clicks'),
    Input('profit-agg-weekly', 'n_clicks'),
    Input('profit-agg-monthly', 'n_clicks'),
    Input('profit-agg-yearly', 'n_clicks'),
    State('profit-time-agg-state', 'data')
)
def update_profit_agg_state(d, w, m, y, current_state):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_state
    button_id = ctx.triggered [0]['prop_id'].split('.')[0]
    if button_id == 'profit-agg-daily': return 'Daily'
    elif button_id == 'profit-agg-weekly': return 'Weekly'
    elif button_id == 'profit-agg-monthly': return 'Monthly'
    elif button_id == 'profit-agg-yearly': return 'Yearly'
    return current_state

# Callback to update Sales and Profit charts with Corrected Logic & Sustainability Look
# --- Updated Callback with Date Picker Logic ---
@app.callback(
    Output('total-sales-over-time-chart', 'figure'),
    Output('total-profit-over-time-chart', 'figure'),
    Input('stored-data', 'data'),
    Input('sales-time-agg-state', 'data'),
    Input('profit-time-agg-state', 'data'),
    Input('sales-trend-date-picker', 'date') # <-- NEW INPUT
)
def update_sales_and_profit_charts(stored_data_json, sales_time_agg, profit_time_agg, selected_date):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return {}, {}

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')
    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
    df_sales.dropna(subset=['SaleDate'], inplace=True)

    if df_sales.empty:
        return {}, {}

    # Handle Date Picker Input (Default to Today if None)
    if selected_date:
        anchor_date = pd.to_datetime(selected_date).date()
    else:
        anchor_date = datetime.now().date()

    # --- Helper to Filter Data & Create Chart ---
    def create_trend_chart(df, time_agg, value_col, title, line_color='#2eda78'):
        agg_df = pd.DataFrame()
        
        # 1. Filter Logic based on Anchor Date
        if time_agg == 'Daily':
            # Show ONLY the selected date
            # (If your data has times, this shows the hourly trend. If only dates, it shows 1 point)
            agg_df = df[df['SaleDate'].dt.date == anchor_date].copy()
            # If empty (no sales on selected day), chart remains empty (correct behavior)
            agg_df = agg_df.groupby('SaleDate')[value_col].sum().reset_index()
            agg_df.rename(columns={'SaleDate': 'Date'}, inplace=True)
            tick_format = "%H:%M" # Assume hourly if data allows

        elif time_agg == 'Weekly':
            # Show 7 days ENDING on selected date
            start_date = pd.to_datetime(anchor_date) - timedelta(days=6)
            mask = (df['SaleDate'] >= start_date) & (df['SaleDate'].dt.date <= anchor_date)
            filtered_df = df[mask].copy()
            agg_df = filtered_df.groupby('SaleDate')[value_col].sum().reset_index()
            agg_df.rename(columns={'SaleDate': 'Date'}, inplace=True)
            tick_format = "%d %b" # e.g. 04 Feb

        elif time_agg == 'Monthly':
            # Show the FULL month of the selected date
            mask = (df['SaleDate'].dt.month == anchor_date.month) & (df['SaleDate'].dt.year == anchor_date.year)
            filtered_df = df[mask].copy()
            agg_df = filtered_df.groupby('SaleDate')[value_col].sum().reset_index()
            agg_df.rename(columns={'SaleDate': 'Date'}, inplace=True)
            tick_format = "%d %b"

        elif time_agg == 'Yearly':
            # Show the FULL year of the selected date
            mask = (df['SaleDate'].dt.year == anchor_date.year)
            filtered_df = df[mask].copy()
            # Group by Month for yearly view
            filtered_df['MonthPeriod'] = filtered_df['SaleDate'].dt.to_period('M').dt.to_timestamp()
            agg_df = filtered_df.groupby('MonthPeriod')[value_col].sum().reset_index()
            agg_df.rename(columns={'MonthPeriod': 'Date'}, inplace=True)
            tick_format = "%b" # Jan, Feb...

        # 2. Build Figure
        fig = {
            'data': [
                go.Scatter(
                    x=agg_df['Date'],
                    y=agg_df[value_col],
                    mode='lines+markers' if len(agg_df) < 2 else 'lines',
                    fill='tozeroy',
                    line=dict(color=line_color, width=4, shape='spline'),
                    fillcolor='rgba(46, 218, 120, 0.05)',
                    name=title
                )
            ],
            'layout': {
                'title': {
                    'text': title,
                    'font': {'size': 16, 'color': '#6c757d', 'weight': 'bold'}
                },
                'xaxis': {
                    'tickformat': tick_format,
                    'showgrid': False, 'showline': False, 'zeroline': False,
                    'tickfont': {'color': '#adb5bd', 'size': 11, 'weight': 'bold'},
                    'fixedrange': True
                },
                'yaxis': {
                    'showgrid': False, 'showline': False, 'zeroline': False,
                    'showticklabels': False, 'fixedrange': True
                },
                'plot_bgcolor': 'white',
                'paper_bgcolor': 'white',
                'margin': {'l': 0, 'r': 0, 't': 40, 'b': 20},
                'height': 300,
                'showlegend': False,
                'hovermode': 'x unified'
            }
        }
        return fig

    # Create Charts
    sales_fig = create_trend_chart(df_sales, sales_time_agg, 'TotalPrice', 'Overall Sales Growth')
    profit_fig = create_trend_chart(df_sales, profit_time_agg, 'Profit', 'Overall Profit Growth')

    return sales_fig, profit_fig

@app.callback(
    Output('sales-total-kpi', 'children'),
    Output('sales-change-kpi', 'children'),
    Output('profit-total-kpi', 'children'),
    Output('profit-change-kpi', 'children'),
    Input('stored-data', 'data'),
    Input('sales-time-agg-state', 'data'), # <-- NEW: Get state from dcc.Store
    Input('profit-time-agg-state', 'data') # <-- NEW: Get state from dcc.Store
)
def update_kpis(stored_data_json, sales_time_agg, profit_time_agg):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return "₹0", "N/A", "₹0", "N/A"

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')
    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
    df_sales.dropna(subset=['SaleDate'], inplace=True)

    if df_sales.empty:
        return "₹0", "N/A", "₹0", "N/A"

    # --- Sales KPI Calculation ---
    sales_agg_current_period_df = aggregate_data(df_sales, sales_time_agg, 'SaleDate', 'TotalPrice')
    current_sales_total = sales_agg_current_period_df['TotalPrice'].iloc[-1] if not sales_agg_current_period_df.empty else 0
    previous_sales_total = sales_agg_current_period_df['TotalPrice'].iloc[-2] if len(sales_agg_current_period_df) >= 2 else 0
    sales_change = 0
    if previous_sales_total != 0:
        sales_change = ((current_sales_total - previous_sales_total) / previous_sales_total) * 100
    formatted_sales_total = f"₹{current_sales_total:,.0f}"
    formatted_sales_change = f"This Period {sales_change:+.1f}%"

    # --- Profit KPI Calculation ---
    profit_agg_current_period_df = aggregate_data(df_sales, profit_time_agg, 'SaleDate', 'Profit')
    current_profit_total = profit_agg_current_period_df['Profit'].iloc[-1] if not profit_agg_current_period_df.empty else 0
    previous_profit_total = profit_agg_current_period_df['Profit'].iloc[-2] if len(profit_agg_current_period_df) >= 2 else 0
    profit_change = 0
    if previous_profit_total != 0:
        profit_change = ((current_profit_total - previous_profit_total) / previous_profit_total) * 100
    formatted_profit_total = f"₹{current_profit_total:,.0f}"
    formatted_profit_change = f"This Period {profit_change:+.1f}%"

    return formatted_sales_total, formatted_sales_change, formatted_profit_total, formatted_profit_change


# Callback to populate the Product Seasonal Dropdown
@app.callback(
    Output('product-seasonal-dropdown', 'options'),
    Output('product-seasonal-dropdown', 'value'),
    Input('stored-data', 'data')
)
def set_product_seasonal_options(stored_data_json):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return [], None

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')

    if 'ProductCategory' not in df_sales.columns:
        print("Warning: 'ProductCategory' column not found in data for product seasonal dropdown.")
        return [], None

    # Get unique product categories and prepare options
    product_categories = sorted(df_sales['ProductCategory'].unique().tolist())
    options = [{'label': category, 'value': category} for category in product_categories]

    # --- Set Default Product ---
    # You can choose a default based on your preference:
    # Option A: The first product in the sorted list (alphabetical)
    default_product = product_categories[0] if product_categories else None

    # Option B: A specific product if it exists (e.g., 'Apparel' or 'Winter Coats')
    # if 'Apparel' in product_categories:
    #     default_product = 'Apparel'
    # elif product_categories:
    #     default_product = product_categories[0]
    # else:
    #     default_product = None

    return options, default_product



# Callback to update Product Seasonal Trends KPI and Chart
@app.callback(
    Output('product-seasonal-kpi', 'children'),
    Output('product-seasonal-chart', 'figure'),
    Input('product-seasonal-dropdown', 'value'),
    Input('seasonal-year-dropdown', 'value'),
    Input('stored-data', 'data')
)
def update_product_seasonal_trends(selected_product, selected_year, stored_data_json):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return "", {}

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')
    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
    df_sales.dropna(subset=['SaleDate'], inplace=True)

    # Re-calculate season/year if not already in stored_data (better to do this in load_data)
    df_sales['Month'] = df_sales['SaleDate'].dt.month
    df_sales['Season'] = df_sales['Month'].apply(get_season)
    df_sales['Year'] = df_sales['SaleDate'].dt.year

    if df_sales.empty or selected_product is None:
        return "$0 (N/A)", {} # Adjusted for INR later

    # Filter by selected product
    # Adjust 'ProductCategory' to 'ProductName' if that's your column
    filtered_df = df_sales[df_sales['ProductCategory'] == selected_product].copy()

    if filtered_df.empty:
        return f"₹0 ({selected_product})", {} # Updated for INR

    # Filter by selected year if applicable. 'current_projected' implies latest year
    if selected_year == 'current_projected':
        current_year = filtered_df['Year'].max() # Get the latest year in data
        period_df = filtered_df[filtered_df['Year'] == current_year]
    else: # If you add other years (e.g., '2023', '2024')
        period_df = filtered_df[filtered_df['Year'] == int(selected_year)]

    if period_df.empty:
        return f"₹0 ({selected_product})", {} # Updated for INR

    # Aggregate by season
    seasonal_order = ['Spring', 'Summer', 'Autumn', 'Winter']
    seasonal_sales = period_df.groupby('Season')['TotalPrice'].sum().reindex(seasonal_order).fillna(0).reset_index()
    seasonal_sales.columns = ['Season', 'Sales']

    # KPI Calculation for current period
    current_total_sales = seasonal_sales['Sales'].sum()

    # To calculate percentage change, you need previous year's total sales for this product
    previous_year = current_year - 1
    previous_year_df = filtered_df[filtered_df['Year'] == previous_year]
    previous_total_sales = previous_year_df['TotalPrice'].sum() if not previous_year_df.empty else 0

    sales_change_percent = 0
    if previous_total_sales != 0:
        sales_change_percent = ((current_total_sales - previous_total_sales) / previous_total_sales) * 100

    # Format KPI
    formatted_kpi = html.Div([
        html.H3(f"₹{current_total_sales:,.0f}", className="text-primary"), # Adjusted for INR
        html.P(f"{selected_product} ({current_year} Sales) {sales_change_percent:+.1f}%",
               className="text-muted")
    ], className="text-center")


    # Create the chart
    colors = ['#28a745' if s >= 0 else '#dc3545' for s in seasonal_sales['Sales']] # Basic color logic
    # More advanced logic for increase/decrease if you have season-over-season change
    # For now, let's just make them all green as per the image for positive sales
    plot_colors = ['#28a745'] * len(seasonal_sales) # All green, match image style

    fig = go.Figure(data=[
        go.Bar(
            x=seasonal_sales['Season'],
            y=seasonal_sales['Sales'],
            marker_color=plot_colors, # Apply colors
            name='Sales'
        )
    ])

    fig.update_layout(
        title={
            'text': f"Product Seasonal Trends ({selected_product})", # Dynamic title
            'font': {'size': 18, 'color': '#333'}
        },
        xaxis=dict(
            title='Season',
            categoryorder='array', # Ensure seasons are in order
            categoryarray=seasonal_order,
            showgrid=False, zeroline=False
        ),
        yaxis=dict(
            title='Sales Amount (₹)', # Adjusted for INR
            showgrid=False, zeroline=False,
            rangemode='tozero' # Ensure bars start from zero
        ),
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='#fff',
        margin={'l': 40, 'r': 20, 't': 60, 'b': 30},
        height=350, # Adjust height as needed
        showlegend=False
    )

    return formatted_kpi, fig

# Callback to populate 'product-brand-product-dropdown' #

@app.callback(
    Output('product-brand-product-dropdown', 'options'),
    Output('product-brand-product-dropdown', 'value'),
    Input('stored-data', 'data')
)
def set_product_brand_product_options(stored_data_json):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return [], None

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')

    if 'ProductCategory' not in df_sales.columns:
        return [], None

    product_categories = sorted(df_sales['ProductCategory'].unique().tolist())
    options = [{'label': category, 'value': category} for category in product_categories]
    
    # Set a default value, e.g., the first product or 'Apparel' if you prefer
    default_value = product_categories[0] if product_categories else None

    return options, default_value

#  Callback to update brand-sales-time-agg-state (for Monthly/Quarterly/Yearly buttons) #
from dash.dependencies import State # Make sure you have this import

@app.callback(
    Output('brand-sales-time-agg-state', 'data'),
    [Input('brand-sales-monthly-btn', 'n_clicks'),
     Input('brand-sales-quarterly-btn', 'n_clicks'),
     Input('brand-sales-yearly-btn', 'n_clicks')]
)
def set_brand_sales_time_agg(monthly_clicks, quarterly_clicks, yearly_clicks):
    ctx = dash.callback_context

    if not ctx.triggered:
        return 'Monthly' # Default value if no button has been clicked yet

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'brand-sales-monthly-btn':
        return 'Monthly'
    elif button_id == 'brand-sales-quarterly-btn':
        return 'Quarterly'
    elif button_id == 'brand-sales-yearly-btn':
        return 'Yearly'
    return 'Monthly' # Fallback


# Callback to generate 'product-brand-sales-chart'
# Ensure you have plotly.graph_objects as go
import plotly.graph_objects as go
import plotly.express as px # Often useful for bar charts


@app.callback(
    Output('product-brand-sales-chart', 'figure'),
    [Input('product-brand-product-dropdown', 'value'),
     Input('product-brand-year-dropdown', 'value'),
     Input('product-brand-quarter-dropdown', 'value'),
     Input('product-brand-month-dropdown', 'value')],
    [State('stored-data', 'data')]
)
def update_product_brand_sales_chart(
    selected_product_category,
    selected_year,
    selected_quarter,
    selected_month,
    stored_data_json
):
    # Initialize an empty figure to return in case of no data
    empty_figure = go.Figure().update_layout(
        title="No data to display. Please adjust filters.",
        xaxis={'visible': False},
        yaxis={'visible': False}
    )

    if stored_data_json is None or 'sales' not in stored_data_json:
        return empty_figure.update_layout(title="No sales data loaded.")

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')

    if 'SaleDate' not in df_sales.columns:
        return empty_figure.update_layout(title="Error: 'SaleDate' column missing in your data.")

    df_sales['SaleDate'] = pd.to_datetime(df_sales['SaleDate'], errors='coerce')
    df_sales.dropna(subset=['SaleDate'], inplace=True)

    if df_sales.empty:
        return empty_figure.update_layout(title="Loaded sales data is empty after date processing.")

    if selected_product_category is None:
        return empty_figure.update_layout(title="Please select a Product Category to view sales data.")

    if 'Brand' not in df_sales.columns:
        return empty_figure.update_layout(title="Error: 'Brand' column missing in your sales data.")

    # Apply product category filter first
    filtered_df = df_sales[df_sales['ProductCategory'] == selected_product_category].copy()

    # Apply time filters
    if selected_year is not None:
        filtered_df = filtered_df[filtered_df['SaleDate'].dt.year == selected_year]
    if selected_quarter is not None:
        filtered_df = filtered_df[filtered_df['SaleDate'].dt.quarter == selected_quarter]
    if selected_month is not None:
        filtered_df = filtered_df[filtered_df['SaleDate'].dt.month == selected_month]

    # --- Crucial: If filtered_df is empty after all filters, return early ---
    if filtered_df.empty:
        return empty_figure.update_layout(
            title=f"No data for '{selected_product_category}' with current time filters."
        )

    # --- Determine the 'Period' column based on the most specific filter ---
    facet_col_name = 'Period' # Default facet column name for consistency
    aggregation_level_title = ""

    if selected_month is not None:
        filtered_df['Period'] = filtered_df['SaleDate'].dt.to_period('M').astype(str)
        aggregation_level_title = "Monthly"
    elif selected_quarter is not None:
        filtered_df['Period'] = filtered_df['SaleDate'].dt.to_period('Q').astype(str)
        aggregation_level_title = "Quarterly"
    elif selected_year is not None:
        filtered_df['Period'] = filtered_df['SaleDate'].dt.to_period('Y').astype(str)
        aggregation_level_title = "Yearly"
    else:
        # Default: if no specific time filter is selected, aggregate yearly
        filtered_df['Period'] = filtered_df['SaleDate'].dt.to_period('Y').astype(str)
        aggregation_level_title = "Overall Yearly"

    # --- THIS IS THE MISSING/CRITICAL PART ---
    # Aggregate sales by Brand and Period
    aggregated_df = filtered_df.groupby(['Brand', 'Period'])['TotalPrice'].sum().reset_index()

    # If aggregation itself results in an empty DataFrame (unlikely but possible if all data was NaN after grouping)
    if aggregated_df.empty:
        return empty_figure.update_layout(
            title=f"No aggregated data for {selected_product_category} with current filters after grouping."
        )

    # Sort brands by TotalPrice within each Period for better visualization
    aggregated_df = aggregated_df.sort_values(by=['Period', 'TotalPrice'], ascending=[True, True])

    # Create the horizontal bar chart
    fig = px.bar(
        aggregated_df,
        y='Brand',
        x='TotalPrice',
        color='Brand',
        facet_col=facet_col_name,
        facet_col_wrap=1,
        title=f"Sales by Brand for {selected_product_category} ({aggregation_level_title} Aggregation)",
        labels={'TotalPrice': 'Total Sales (₹)', 'Brand': 'Brand'},
        orientation='h',
        height=800,
        # Add text_auto for displaying values on bars. 'auto' tries to format nicely.
        # You can also specify a format string like '$,.0f' for currency, or '.2s' for SI units.
        text_auto=True,
        # 'text' argument can be used if you need custom formatting beyond text_auto
        # For example, to add '₹' symbol: text=aggregated_df['TotalPrice'].apply(lambda x: f"₹{x:,.0f}")
    )

    # --- OPTIONAL: Adjust text properties for better visibility ---
    fig.update_traces(textposition='outside') # Positions text outside the bars
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide') # Helps with crowded bars

    # Update layout for better readability
    fig.update_layout(
        margin={"t": 60, "b": 0, "l": 0, "r": 0},
        xaxis_title='Total Sales (₹)',
        yaxis_title=None,
        hovermode="y unified"
    )
    fig.update_yaxes(matches=None, showticklabels=True, automargin=True)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))

    return fig

# New callback for year dropdown
@app.callback(
    Output('product-brand-year-dropdown', 'options'),
    Output('product-brand-year-dropdown', 'value'), # Optional: Set a default year
    Input('stored-data', 'data')
)
def set_product_brand_year_options(stored_data_json):
    if stored_data_json is None or 'sales' not in stored_data_json:
        return [], None

    df_sales = pd.read_json(io.StringIO(stored_data_json['sales']), orient='split')

    if 'Year' not in df_sales.columns:
        print("Warning: 'Year' column not found in data for brand sales year dropdown.")
        return [], None

    # Get unique years, sort them, and prepare options
    years = sorted(df_sales['Year'].unique().tolist(), reverse=True)
    options = [{'label': str(year), 'value': year} for year in years]

    # Set default to the latest year, or None if you prefer no default
    default_year = max(years) if years else None

    return options, default_year



# --- Helper for Sustainability Chart ---
def get_sustainability_chart():
    # Dummy data to match the curve in your image
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    # These values create the specific "dip then rise" curve shown
    values = [1500, 1550, 2800, 2400, 3200, 3600, 4800] 

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days,
        y=values,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#2eda78', width=4, shape='spline'), # The bright green spline
        fillcolor='rgba(46, 218, 120, 0.05)' # Very faint green fill
    ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, showline=False, zeroline=False, tickfont=dict(color='#adb5bd', size=11, weight='bold'), fixedrange=True),
        yaxis=dict(showgrid=False, showline=False, zeroline=False, showticklabels=False, fixedrange=True),
        height=280,
        showlegend=False,
        hovermode='x unified'
    )
    return fig

# --- Sustainability Layout Definition ---
sustainability_layout = html.Div(className="sustainability-content p-4", children=[
    
    # 1. Header
    dbc.Row(className="mb-4 align-items-center", children=[
        dbc.Col([
            html.H2("Sustainability Tracker", className="fw-bolder mb-1"),
            html.P("Real-time environmental impact analysis and AI-driven reduction strategies.", className="text-muted")
        ], md=8),
        dbc.Col([
            dbc.Button([html.I(className="bi bi-share me-2"), "Share"], color="light", className="sus-header-btn me-2 border"),
            dbc.Button([html.I(className="bi bi-download me-2"), "Download Report"], color="success", className="sus-header-btn")
        ], md=4, className="d-flex justify-content-end")
    ]),

    # 2. Top Metrics (3 Cards)
    dbc.Row(className="mb-4 g-4", children=[
        # Card 1: Carbon Footprint
        dbc.Col(md=4, children=[
            dbc.Card(className="sus-card border-2 border-success border-opacity-25", style={'backgroundColor': '#f0fdf4'}, children=[ # Light green bg hint
                dbc.CardBody(className="sus-card-body position-relative", children=[
                    html.Div("CO₂", className="co2-watermark"), # Watermark
                    html.Div("CURRENT CARBON FOOTPRINT", className="metric-title-sus text-success"),
                    html.Div([
                        html.Span("42.5 tons", className="metric-value-sus"),
                        html.Span(" CO2e", className="fs-5 text-muted ms-1")
                    ], className="position-relative", style={'zIndex': '1'}),
                    html.Div([
                        html.I(className="bi bi-graph-down-arrow me-2"), " -12% from last month"
                    ], className="text-danger fw-bold mt-2")
                ])
            ])
        ]),
        # Card 2: Waste Diverted
        dbc.Col(md=4, children=[
            dbc.Card(className="sus-card", children=[
                dbc.CardBody(className="sus-card-body", children=[
                    html.Div("WASTE DIVERTED", className="metric-title-sus"),
                    html.Div("12.8 tons", className="metric-value-sus"),
                    html.Div([
                        html.I(className="bi bi-graph-up-arrow me-2"), " +5% target pace"
                    ], className="text-success fw-bold mt-2")
                ])
            ])
        ]),
        # Card 3: Sustainability Score
        dbc.Col(md=4, children=[
            dbc.Card(className="sus-card", children=[
                dbc.CardBody(className="sus-card-body", children=[
                    html.Div("SUSTAINABILITY SCORE", className="metric-title-sus"),
                    dbc.Row([
                        dbc.Col(html.Div("88/100", className="metric-value-sus"), width="auto"),
                        dbc.Col(html.Div(className="sus-progress-container mt-3", children=[
                            html.Div(className="sus-progress-bar", style={'width': '88%'})
                        ]))
                    ]),
                    html.Div("Top 5% in your industry", className="text-success fw-bold mt-2")
                ])
            ])
        ]),
    ]),

    # 3. Trends & Materials Section (With Interactive Buttons)
    dbc.Card(className="sus-card mb-4", children=[
        dbc.CardBody(className="p-4", children=[
            dbc.Row([
                # Left: Chart
                dbc.Col(md=8, children=[
                    dbc.Row([
                        dbc.Col([
                            html.H5("Historical Wastage Trends", className="fw-bold"),
                            html.P("Comparing physical waste volume against sustainability targets.", className="text-muted small")
                        ]),
                        dbc.Col([
                            dbc.ButtonGroup([
                                dbc.Button("Weekly", id="sus-btn-weekly", color="light", className="fw-bold border", n_clicks=0),
                                dbc.Button("Monthly", id="sus-btn-monthly", color="light", className="fw-bold border", n_clicks=0),
                                dbc.Button("Yearly", id="sus-btn-yearly", color="light", className="fw-bold border", n_clicks=0),
                            ], size="sm")
                        ], className="text-end")
                    ]),
                    html.Div([
                        html.Span("2,450 kg", id="sus-total-waste", className="display-6 fw-bold me-3"),
                        dbc.Badge("-8.4% vs prev. period", id="sus-trend-badge", color="danger", className="p-2 opacity-75")
                    ], className="mt-3 mb-2"),
                    dcc.Graph(id="sus-trend-graph", config={'displayModeBar': False})
                ]),
                
                # Right: Material Breakdown
                dbc.Col(md=4, className="ps-md-5 pt-3", children=[
                    html.H6("WASTE BY MATERIAL", className="metric-title-sus mb-4"),
                    
                    html.Div(className="mb-4", children=[
                        html.Div(["Plastic", html.Span("42%", className="float-end fw-bold")], className="mb-1 fw-bold font-monospace small"),
                        html.Div(className="sus-progress-container", children=[html.Div(className="sus-progress-bar", style={'width': '42%'})])
                    ]),
                    html.Div(className="mb-4", children=[
                        html.Div(["Paper & Cardboard", html.Span("28%", className="float-end fw-bold")], className="mb-1 fw-bold font-monospace small"),
                        html.Div(className="sus-progress-container", children=[html.Div(className="sus-progress-bar", style={'width': '28%'})])
                    ]),
                    html.Div(className="mb-4", children=[
                        html.Div(["Food Waste", html.Span("18%", className="float-end fw-bold")], className="mb-1 fw-bold font-monospace small"),
                        html.Div(className="sus-progress-container", children=[html.Div(className="sus-progress-bar", style={'width': '18%'})])
                    ]),
                    html.Div(className="mb-4", children=[
                        html.Div(["Metal", html.Span("12%", className="float-end fw-bold")], className="mb-1 fw-bold font-monospace small"),
                        html.Div(className="sus-progress-container", children=[html.Div(className="sus-progress-bar", style={'width': '12%'})])
                    ]),
                    
                    html.A([html.I(className="bi bi-arrow-right"), " View Full Analytics"], href="#", className="text-success fw-bold text-decoration-none small")
                ])
            ])
        ])
    ]),

    # 4. AI Tips
    html.Div([
        html.H4([html.I(className="bi bi-stars text-success me-2"), "AI-Powered Sustainability Tips"], className="fw-bold mb-4"),
        dbc.Row(className="g-4", children=[
            # Tip 1
            dbc.Col(md=4, children=[
                dbc.Card(className="sus-card ai-tip-card", children=[
                    dbc.CardBody([
                        html.Div([html.I(className="bi bi-truck fs-4 text-success"), html.Span("HIGH IMPACT", className="tip-badge badge-high-impact float-end")]),
                        html.H6("Route Optimization", className="fw-bold mt-3"),
                        html.P("AI detected that consolidating shipments from Supplier B could reduce transport emissions by 14.2% monthly.", className="text-muted small mt-2"),
                        dbc.Button("Apply Optimization", className="tip-button")
                    ])
                ])
            ]),
            # Tip 2
            dbc.Col(md=4, children=[
                dbc.Card(className="sus-card ai-tip-card", children=[
                    dbc.CardBody([
                        html.Div([html.I(className="bi bi-box-seam fs-4 text-success"), html.Span("SUPPLY CHAIN", className="tip-badge badge-supply-chain float-end")]),
                        html.H6("Packaging Upgrade", className="fw-bold mt-3"),
                        html.P("Switching to biodegradable filler for SKU group \"Electronics\" would divert 450kg of plastic from landfills annually.", className="text-muted small mt-2"),
                        dbc.Button("View Suppliers", className="tip-button")
                    ])
                ])
            ]),
            # Tip 3
            dbc.Col(md=4, children=[
                dbc.Card(className="sus-card ai-tip-card", children=[
                    dbc.CardBody([
                        html.Div([html.I(className="bi bi-lightning-charge fs-4 text-success"), html.Span("OPERATIONAL", className="tip-badge badge-operational float-end")]),
                        html.H6("Energy Efficiency", className="fw-bold mt-3"),
                        html.P("Inventory turnover is highest between 10 AM and 2 PM. Adjust warehouse climate controls outside these peak hours.", className="text-muted small mt-2"),
                        dbc.Button("Setup Schedule", className="tip-button")
                    ])
                ])
            ]),
        ])
    ], className="mb-5"),

    # 5. Waste Leaders Table
    dbc.Card(className="sus-card mb-5", children=[
        dbc.CardBody([
            html.H5("Inventory Waste Leaders", className="fw-bold mb-4 ps-3"),
            dash_table.DataTable(
                id='waste-leaders-table',
                columns=[
                    {'name': 'PRODUCT ITEM', 'id': 'item'},
                    {'name': 'CATEGORY', 'id': 'cat'},
                    {'name': 'WASTE MASS', 'id': 'mass'},
                    {'name': 'IMPACT SCORE', 'id': 'score'},
                    {'name': 'ACTION', 'id': 'action'},
                ],
                data=[
                    {'item': 'Eco-Poly Packaging Film', 'cat': 'Packaging', 'mass': '842 kg', 'score': 'CRITICAL', 'action': 'Mitigate'},
                    {'item': 'Standard A4 Printer Paper', 'cat': 'Office Supplies', 'mass': '215 kg', 'score': 'MODERATE', 'action': 'Mitigate'},
                    {'item': 'Organic Cotton T-Shirts (Defective)', 'cat': 'Apparel', 'mass': '112 kg', 'score': 'LOW', 'action': 'Mitigate'},
                ],
                style_table={'overflowX': 'auto'},
                style_data_conditional=[
                    {'if': {'column_id': 'cat'}, 'color': '#2eda78', 'fontWeight': '600'},
                    {'if': {'column_id': 'action'}, 'color': '#28a745', 'fontWeight': 'bold', 'cursor': 'pointer', 'textAlign': 'right'},
                    
                    # Badges Logic
                    {'if': {'filter_query': '{score} = "CRITICAL"', 'column_id': 'score'}, 
                     'backgroundColor': '#ffe5e5', 'color': '#c92a2a', 'fontWeight': '800', 'borderRadius': '4px', 'padding': '5px', 'fontSize': '0.7rem'},
                    
                    {'if': {'filter_query': '{score} = "MODERATE"', 'column_id': 'score'}, 
                     'backgroundColor': '#fff3bf', 'color': '#f08c00', 'fontWeight': '800', 'borderRadius': '4px', 'padding': '5px', 'fontSize': '0.7rem'},

                    {'if': {'filter_query': '{score} = "LOW"', 'column_id': 'score'}, 
                     'backgroundColor': '#d3f9d8', 'color': '#2b8a3e', 'fontWeight': '800', 'borderRadius': '4px', 'padding': '5px', 'fontSize': '0.7rem'},
                ]
            )
        ])
    ]),

    # Footer
    html.Div(className="text-center text-muted small py-4", children=[
        html.Span(""),
        html.Span("", className="ms-4 cursor-pointer"),
        html.Span("", className="ms-3 cursor-pointer"),
        html.Span("", className="ms-3 cursor-pointer"),
    ])
])

# --- Callback for Sustainability Trends Chart Switching ---
@app.callback(
    [Output("sus-trend-graph", "figure"),
     Output("sus-total-waste", "children"),
     Output("sus-trend-badge", "children"),
     Output("sus-trend-badge", "color"),
     Output("sus-btn-weekly", "active"),
     Output("sus-btn-monthly", "active"),
     Output("sus-btn-yearly", "active")],
    [Input("sus-btn-weekly", "n_clicks"),
     Input("sus-btn-monthly", "n_clicks"),
     Input("sus-btn-yearly", "n_clicks")]
)
def update_sustainability_trends(btn_w, btn_m, btn_y):
    ctx = dash.callback_context
    button_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else "sus-btn-weekly"

    # Default to Weekly Data (The layout from your image)
    x_data = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    y_data = [1500, 1550, 2800, 2400, 3200, 3600, 4800]
    total_val = "2,450 kg"
    badge_text = "-8.4% vs prev. week"
    badge_color = "danger"
    
    # Button States
    is_w, is_m, is_y = True, False, False

    # Switch Data based on button click
    if button_id == "sus-btn-monthly":
        x_data = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
        y_data = [10500, 9800, 11200, 8900] # Monthly dummy data
        total_val = "10.1 tons"
        badge_text = "+1.2% vs prev. month"
        badge_color = "success"
        is_w, is_m, is_y = False, True, False

    elif button_id == "sus-btn-yearly":
        x_data = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        y_data = [42, 40, 38, 35, 36, 32, 30, 28, 25, 24, 22, 20] # Yearly trend (downwards is good for waste!)
        total_val = "372 tons"
        badge_text = "-15% vs prev. year"
        badge_color = "success"
        is_w, is_m, is_y = False, False, True

    # Build the Figure
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_data,
        y=y_data,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#2eda78', width=4, shape='spline'),
        fillcolor='rgba(46, 218, 120, 0.05)'
    ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, showline=False, zeroline=False, tickfont=dict(color='#adb5bd', size=11, weight='bold'), fixedrange=True),
        yaxis=dict(showgrid=False, showline=False, zeroline=False, showticklabels=False, fixedrange=True),
        height=280,
        showlegend=False,
        hovermode='x unified'
    )

    return fig, total_val, badge_text, badge_color, is_w, is_m, is_y
    
if __name__ == '__main__':
    app.run(debug=True)













