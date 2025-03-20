import streamlit as st
import mysql.connector
import os
import pandas as pd
from dotenv import load_dotenv
import plotly.express as px

# Load environment variables from .env file (for local development)
load_dotenv()

# Get DB credentials securely from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")  # Default to 3306 if not set
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Function to fetch trading data from MySQL
def get_trade_metrics():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Get distinct trader count
        cursor.execute("SELECT COUNT(DISTINCT id) FROM trades")
        distinct_traders = cursor.fetchone()[0]

        # Get distinct forex pairs & target pairs count
        cursor.execute("SELECT COUNT(DISTINCT CONCAT(forex_pair, target_pair)) FROM trades")
        distinct_forex_pairs = cursor.fetchone()[0]

        # Get distinct providers count
        cursor.execute("SELECT COUNT(DISTINCT provider) FROM trades")
        distinct_providers = cursor.fetchone()[0]

        # Get Buy vs Sell count
        cursor.execute("SELECT action, COUNT(*) FROM trades GROUP BY action")
        action_counts = dict(cursor.fetchall())
        buy_count = action_counts.get('Buy', 0)
        sell_count = action_counts.get('Sell', 0)

        # Get Active vs Non-Active trade count
        cursor.execute("SELECT status, COUNT(*) FROM trades GROUP BY status")
        status_counts = dict(cursor.fetchall())
        active_count = status_counts.get('Active', 0)
        non_active_count = sum(status_counts.values()) - active_count

        # Get Profit & Loss Counts
        cursor.execute("SELECT profit_status, COUNT(*) FROM trades GROUP BY profit_status")
        profit_loss_counts = dict(cursor.fetchall())
        profit_count = profit_loss_counts.get('Profit', 0)
        loss_count = profit_loss_counts.get('Loss', 0)

        # ✅ Compute Accuracy: (Profit / (Profit + Loss)) * 100
        total_trades = profit_count + loss_count
        accuracy = (((profit_count) / (total_trades)) * 100) if total_trades > 0 else 0
        
        
        cursor.execute("SELECT 'profit' as status,COUNT(*) FROM trades where status = 'Active' and current_profit_loss > 0")
        profitActiveCounts = dict(cursor.fetchall())
        profitActivecount = profitActiveCounts.get('profit', 0)
        
        cursor.execute("SELECT 'loss' as status,COUNT(*) FROM trades where status = 'Active' and current_profit_loss < 0")
        lossActiveCounts = dict(cursor.fetchall())
        lossActivecount = lossActiveCounts.get('loss', 0)
        
        activeaccuracy = (profitActivecount/(lossActivecount+profitActivecount))*100

        conn.close()

        return {
            "distinct_traders": distinct_traders,
            "distinct_forex_pairs": distinct_forex_pairs,
            "distinct_providers": distinct_providers,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "active_count": active_count,
            "non_active_count": non_active_count,
            "accuracy": accuracy,
            "activeaccuracy": activeaccuracy
        }

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return {}

# Streamlit UI
st.set_page_config(page_title="Trading Dashboard", layout="wide")
st.title("📈 Trading Dashboard")

# Fetch metrics from database
metrics = get_trade_metrics()

if metrics:
    col1, col2, col3, col4 = st.columns(4)

    # Display KPIs
    col1.metric(label="Total Number of Signals", value=f"{metrics['distinct_traders']}")
    col1.metric(label="Distinct Pairs Tracked", value=f"{metrics['distinct_forex_pairs']}")
    col1.metric(label="Distinct Providers", value=f"{metrics['distinct_providers']}")

    col2.metric(label="Buy Signals", value=f"{metrics['buy_count']}")
    col2.metric(label="Sell Signals", value=f"{metrics['sell_count']}")
    col2.metric(label="Open Trades", value=f"{metrics['active_count']}")
    col2.metric(label="Closed Trades", value=f"{metrics['non_active_count']}")

    col3.metric(label="Trading Closed Accuracy (%)", value=f"{metrics['accuracy']:.2f}%")  # ✅ Accuracy KPI
    col3.metric(label="Trading Open Accuracy (%)", value=f"{metrics['activeaccuracy']:.2f}%")  # ✅ Accuracy KPI

st.write("✅ Data fetched securely from MySQL and displayed in real-time.")

#%%

# Function to fetch distinct traders per day using created_at
def get_traders_per_day():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Query to get distinct traders per day using created_at
        query = """
        SELECT DATE(created_at) as trade_date, COUNT(DISTINCT id) as distinct_traders 
        FROM trades 
        WHERE created_at IS NOT NULL
        GROUP BY trade_date 
        ORDER BY trade_date ASC
        """
        cursor.execute(query)
        trade_data = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df_trades = pd.DataFrame(trade_data, columns=["trade_date", "distinct_traders"])

        # 🚀 **Fix: Convert trade_date to datetime**
        df_trades["trade_date"] = pd.to_datetime(df_trades["trade_date"], format="%Y-%m-%d")

        return df_trades

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame(columns=["trade_date", "distinct_traders"])

# Fetch data for line graph
df_trades = get_traders_per_day()

# Fix X-axis display
if not df_trades.empty:
    st.subheader("📊 Number of Signals Per Day")
    
    fig = px.line(df_trades, 
                  x="trade_date", 
                  y="distinct_traders", 
                  title="Distinct Signals Per Day",
                  labels={"trade_date": "Date", "distinct_traders": "Number of Traders"},
                  markers=True)  # Add dots on points for better visibility
    
    fig.update_xaxes(
        type="date", 
        tickformat="%Y-%m-%d",  # Format for better readability
        title_text="Date",
        showgrid=True
    )
    
    fig.update_yaxes(
        title_text="Number of Signals",
        showgrid=True
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠ No data available for the line graph.")

#%%


# Function to fetch average profit/loss per trade per provider
def get_avg_profit_loss():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Query to get average profit/loss per trade per provider
        query = """
        SELECT provider, AVG(current_profit_loss) as avg_profit_loss_per_trade
        FROM trades
        WHERE current_profit_loss IS NOT NULL
        AND status != 'Active'
        GROUP BY provider
        ORDER BY avg_profit_loss_per_trade DESC
        """
        cursor.execute(query)
        profit_loss_data = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df_profit_loss = pd.DataFrame(profit_loss_data, columns=["provider", "avg_profit_loss_per_trade"])
        
        return df_profit_loss

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame(columns=["provider", "avg_profit_loss_per_trade"])

# Fetch data
df_profit_loss = get_avg_profit_loss()


# ✅ Debugging: Ensure data is correctly formatted
st.write("📊 Data Preview (Avg Profit/Loss per Trade by Provider):")
st.write(df_profit_loss)

# ✅ Ensure `provider` names are properly cleaned
df_profit_loss["provider"] = df_profit_loss["provider"].astype(str).str.strip()

# Ensure data is not empty before plotting
if not df_profit_loss.empty:
    st.subheader("📊 Average Profit/Loss per Trade by Provider")

    # ✅ Create a sorted bar chart
    fig = px.bar(df_profit_loss, 
                 x="provider", 
                 y="avg_profit_loss_per_trade", 
                 title="Average Profit/Loss % per Trade by Provider",
                 labels={"provider": "Provider", "avg_profit_loss_per_trade": "Avg Profit/Loss per Trade"},
                 text_auto=".2f",  # Show values on bars
                 color="avg_profit_loss_per_trade",  # Color based on profit/loss
                 color_continuous_scale="Viridis")  # Customize colors
    
    # ✅ Adjust x-axis for readability
    fig.update_xaxes(title_text="Provider", tickangle=-45)  # Rotate provider names if long
    
    # ✅ Adjust y-axis
    fig.update_yaxes(title_text="Average Profit/Loss per Trade")

    # Show the plot
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠ No data available for profit/loss.")
    
    #%%




def get_provider_accuracy():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # ✅ Fixed SQL Query for MySQL Compatibility
        query = """
        SELECT provider, 
               COUNT(CASE WHEN profit_status = 'Profit' THEN 1 END) AS profit_count,
               COUNT(CASE WHEN profit_status = 'Loss' THEN 1 END) AS loss_count,
               (COUNT(CASE WHEN profit_status = 'Profit' THEN 1 END) / 
                NULLIF(COUNT(CASE WHEN profit_status IN ('Profit', 'Loss') THEN 1 END), 0)) * 100 AS accuracy
        FROM trades
        WHERE provider IS NOT NULL
        GROUP BY provider
        HAVING COUNT(CASE WHEN profit_status IN ('Profit', 'Loss') THEN 1 END) > 0
        ORDER BY accuracy DESC
        """
        cursor.execute(query)
        accuracy_data = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df_accuracy = pd.DataFrame(accuracy_data, columns=["provider", "profit_count", "loss_count", "accuracy"])

        # ✅ Ensure provider names are properly cleaned
        df_accuracy["provider"] = df_accuracy["provider"].astype(str).str.strip()

        return df_accuracy

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame(columns=["provider", "profit_count", "loss_count", "accuracy"])

# Fetch data
df_accuracy = get_provider_accuracy()

# ✅ Debugging: Ensure data is correctly formatted
st.write("📊 Data Preview (Provider Closed Signals Accuracy %):")
st.write(df_accuracy)

# Ensure data is not empty before plotting
if not df_accuracy.empty:
    st.subheader("📊 Provider Closed Signals Accuracy (% Profit Trades)")

    # ✅ Create a sorted bar chart
    fig = px.bar(df_accuracy, 
                 x="provider", 
                 y="accuracy", 
                 title="Provider Accuracy (% Closed Signals Profit Trades)",
                 labels={"provider": "Provider", "accuracy": "Accuracy (%)"},
                 text_auto=".2f",  # Show values on bars
                 color="accuracy",  # Color based on accuracy
                 color_continuous_scale="Blues")  # Customize colors
    
    # ✅ Adjust x-axis for readability
    fig.update_xaxes(title_text="Provider", tickangle=-45)  # Rotate provider names if long
    
    # ✅ Adjust y-axis
    fig.update_yaxes(title_text="Accuracy (%)")

    # Show the plot
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠ No data available for provider accuracy.")
    
    
    #%%
    
    


# Function to fetch total profit/loss per provider
def get_total_profit_loss():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # ✅ SQL Query to calculate total profit/loss per provider
        query = """
        SELECT provider, 
        SUM(current_profit_loss) AS total_profit_loss
        FROM trades
        WHERE provider IS NOT NULL 
        AND current_profit_loss IS NOT NULL
        AND status != 'Active'
        GROUP BY provider
        ORDER BY total_profit_loss DESC
        """
        cursor.execute(query)
        profit_loss_data = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df_profit_loss = pd.DataFrame(profit_loss_data, columns=["provider", "total_profit_loss"])

        # ✅ Ensure provider names are properly cleaned
        df_profit_loss["provider"] = df_profit_loss["provider"].astype(str).str.strip()

        return df_profit_loss

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame(columns=["provider", "total_profit_loss"])


# Fetch data
df_total_profit_loss = get_total_profit_loss()

# ✅ Debugging: Ensure data is correctly formatted
st.write("📊 Data Preview (Total Closed Profit/Loss per Provider):")
st.write(df_total_profit_loss)

# ✅ Increase graph height dynamically based on number of providers
num_providers = len(df_total_profit_loss)
graph_height = max(800, num_providers * 30)  # ✅ Adjust height based on number of rows

# Ensure data is not empty before plotting
if not df_total_profit_loss.empty:
    st.subheader("📊 Total Closed Profit/Loss per Provider")

    # ✅ Create a sorted bar chart with a fixed scale
    fig = px.bar(df_total_profit_loss, 
                 x="provider", 
                 y="total_profit_loss", 
                 title="Total Closed Profit/Loss per Provider",
                 labels={"provider": "Provider", "total_profit_loss": "Total Profit/Loss"},
                 text_auto=".2f",  # Show values on bars
                 color="total_profit_loss",  # Color based on profit/loss
                 color_continuous_scale="RdYlGn",  # Red for loss, Green for profit
                 height=graph_height)  # ✅ Dynamically adjust height

    # ✅ Adjust x-axis for readability
    fig.update_xaxes(title_text="Provider", tickangle=-45)  # Rotate provider names if long
    
    # ✅ Fix y-axis scale (Keep all bars visible)
    min_y = df_total_profit_loss["total_profit_loss"].min() * 1.1  # 10% padding
    max_y = df_total_profit_loss["total_profit_loss"].max() * 1.1  # 10% padding
    fig.update_yaxes(title_text="Total Profit/Loss", range=[min_y, max_y])

    # Show the plot
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠ No data available for total profit/loss.")



#%%

# Function to fetch performance by base pair / target pair (Average Profit/Loss)
def get_basepair_performance():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # ✅ SQL Query to calculate average profit/loss per base pair & target pair
        query = """
        SELECT forex_pair, target_pair, 
        AVG(current_profit_loss) AS avg_profit_loss
        FROM trades
        WHERE forex_pair IS NOT NULL 
        AND target_pair IS NOT NULL 
        AND current_profit_loss IS NOT NULL
        AND status != 'Active'
        GROUP BY forex_pair, target_pair
        ORDER BY avg_profit_loss DESC
        """
        cursor.execute(query)
        basepair_data = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df_basepair = pd.DataFrame(basepair_data, columns=["forex_pair", "target_pair", "avg_profit_loss"])

        # ✅ Create a combined pair name for better visualization
        df_basepair["pair"] = df_basepair["forex_pair"] + " / " + df_basepair["target_pair"]

        return df_basepair

    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame(columns=["forex_pair", "target_pair", "avg_profit_loss"])

# Fetch data
df_basepair_performance = get_basepair_performance()

# ✅ Debugging: Ensure data is correctly formatted
st.write("📊 Data Preview Closed (Base Pair / Target Pair Performance):")
st.write(df_basepair_performance)

# ✅ Increase graph height dynamically based on number of pairs
num_pairs = len(df_basepair_performance)
graph_height = max(800, num_pairs * 30)  # ✅ Adjust height based on number of rows

# Ensure data is not empty before plotting
if not df_basepair_performance.empty:
    st.subheader("📊 Performance by Base Pair / Target Pair Closed (Average Profit/Loss)")

    # ✅ Create a sorted bar chart
    fig = px.bar(df_basepair_performance, 
                 x="pair", 
                 y="avg_profit_loss", 
                 title="Performance by Base Pair / Target Pair Closed (Average Profit/Loss)",
                 labels={"pair": "Forex Pair / Target Pair", "avg_profit_loss": "Avg Profit/Loss"},
                 text_auto=".2f",  # Show values on bars
                 color="avg_profit_loss",  # Color based on profit/loss
                 color_continuous_scale="Blues",  # Blue gradient for profit/loss
                 height=graph_height)  # ✅ Dynamically adjust height

    # ✅ Adjust x-axis for readability
    fig.update_xaxes(title_text="Forex Pair / Target Pair", tickangle=-45)  # Rotate pair names if long
    
    # ✅ Fix y-axis scale (Keep all bars visible)
    min_y = df_basepair_performance["avg_profit_loss"].min() * 1.1  # 10% padding
    max_y = df_basepair_performance["avg_profit_loss"].max() * 1.1  # 10% padding
    fig.update_yaxes(title_text="Average Profit/Loss", range=[min_y, max_y])

    # Show the plot
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠ No data available for base pair / target pair performance.")

