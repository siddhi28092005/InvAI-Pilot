**InvAI: The Brain Behind Your Inventory**

## **Overview**

InvAI: The Brain Behind Your Inventory is an intelligent web application designed to revolutionize inventory management through the power of Python, Dash, and advanced AI/ML and data science techniques. This interactive dashboard provides comprehensive insights into sales, inventory levels, supplier performance, and more, empowering businesses to make data-driven decisions.

By integrating various data sources such as sales, inventory movements, product information, holidays, promotions, and even weather data, InvAI offers a holistic view of your supply chain operations. It aims to optimize stock levels, predict demand, enhance supplier relationships, and identify opportunities for improved efficiency and sustainability.

## **Features**

InvAI currently offers a robust set of features to monitor and analyze your inventory:

* **Dynamic Dashboard:** Provides an interactive and intuitive interface for real-time data visualization and exploration.  
* **Stock Management:** Real-time tracking of inventory levels for each product and insights into stock movements.  
* **Reorder Recommendations:** Intelligent suggestions for when and how much to reorder based on demand patterns (implicit in "AI/ML and data science" for optimization).  
* **Expiry Management:** Monitoring of products nearing expiry dates to minimize waste.  
* **Sales & Trends Report:** Interactive charts displaying total sales and profit trends over various time periods, with detailed breakdowns and filtering options.  
* **Supplier Performance:** Evaluation of supplier efficiency based on order fulfillment rates and identification of top-performing suppliers.

###

##  

## **Technologies Used**

* **Python:** The core programming language for backend logic, data processing, and AI/ML models.  
* **Dash:** A productive Python framework for building analytical web applications.  
* **Plotly:** Used for creating interactive and visually appealing charts and graphs.  
* **Pandas:** Essential for data manipulation and analysis.  
* **NumPy:** For numerical operations, especially in data processing.  
* **AI/Machine Learning:** Employed for predictive analytics (e.g., demand forecasting, waste prediction) and identifying complex patterns within the data.  
* **Data Science:** Methodologies applied for data cleaning, aggregation, statistical analysis, and deriving actionable insights.

## **Project Structure**

The project is organized as follows:

InvAI/

├── app.py

├── custom.css

├── data/

│   ├── holidays.csv

│   ├── inventory\_movements.csv

│   ├── locations.csv

│   ├── products\_and\_suppliers\_combined.csv

│   ├── promotions.csv

│   ├── purchase\_history.csv

│   ├── sales\_data.csv

│   └── weather\_data.csv

└── README.md

* `app.py`: The main Dash application file, containing the layout, callbacks, and data processing logic.  
* `custom.css`: Custom CSS file for styling the web application.  
* `data/`: Directory containing all the raw CSV data files used by the application.

## **Data Sources**

The application leverages several interconnected datasets to provide comprehensive insights:

* `sales_data.csv`: Contains detailed sales transactions, including product information, quantities, prices, and dates.  
* `inventory_movements.csv`: Records all inbound and outbound inventory movements.  
* `products_and_suppliers_combined.csv`: Provides details about products and their respective suppliers, including expiry dates.  
* `purchase_history.csv`: Tracks purchase orders and their status.  
* `locations.csv`: Information about various store or warehouse locations.  
* `holidays.csv`: Calendar of holidays, which can influence sales patterns.  
* `promotions.csv`: Details of promotional activities and their impact.  
* `weather_data.csv`: Weather information that can be correlated with sales or demand.

## **Setup and Installation**

To run InvAI locally, follow these steps:

1. **Clone the repository**  
   git clone https://github.com/YourGitHubUsername/InvAI.git   
   cd InvAI

     
2. **Create a virtual environment (recommended):**

   python \-m venv venv

            source venv/bin/activate  \# On Windows, use \`venv\\Scripts\\activate\`

3. **Install the required Python packages:**  
   pip install \-r requirements.txt *(Note: You will need to create a `requirements.txt` file. You can generate one using `pip freeze > requirements.txt` after installing all necessary libraries like `dash`, `pandas`, `plotly`, `dash-bootstrap-components`, `numpy`.)*  
4. **Run the application:**  
   python [app.py](http://app.py)  
   Open your web browser and navigate to `http://127.0.0.1:8050/` (or the address displayed in your terminal).

## **Future Enhancements**

InvAI is continuously evolving. The following key features are planned for future development:

* **Scenario Planner:** A dedicated module to simulate different business scenarios (e.g., impact of price changes, promotional campaigns, supply chain disruptions, loyal customers) on inventory levels, sales, and profitability. This will leverage advanced predictive models.  
* **Sustainability Tracker:** A feature to monitor and analyze the environmental impact of inventory operations, including waste reduction, carbon footprint tracking, and opportunities for sustainable practices.

## **Contact**

For any inquiries or feedback, please contact [shubham.yawalkar@adypu.edu.in](mailto:shubham.yawalkar@adypu.edu.in) / [siddhi.shendge@adypu.edu.in](mailto:siddhi.shendge@adypu.edu.in) 

[https://www.linkedin.com/in/shubham-yawalkar/](https://www.linkedin.com/in/shubham-yawalkar/) [https://www.linkedin.com/in/siddhi-shendge-9b4baa25b/](https://www.linkedin.com/in/siddhi-shendge-9b4baa25b/)

