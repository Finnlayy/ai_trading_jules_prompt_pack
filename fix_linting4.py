filepath = 'app/services/perception_engine.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace market_data_service usage with price_poller
content = content.replace("latest_bar = market_data_service.get_latest_bar(symbol)", "current_price = price_poller.get_last_price(symbol) or 0.0")
content = content.replace("current_price = latest_bar['close'] if latest_bar else 0.0", "")

# Add import
if "from app.services.price_poller import price_poller" not in content:
    content = content.replace("from app.services.news_impact_scorer import news_impact_scorer", "from app.services.news_impact_scorer import news_impact_scorer\nfrom app.services.price_poller import price_poller")

with open(filepath, 'w') as f:
    f.write(content)
