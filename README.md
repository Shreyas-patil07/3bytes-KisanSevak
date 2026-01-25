# 🌾 KisanSevak - Smart Agricultural Product Recommendation System

An intelligent chatbot-powered platform that helps farmers find the best agricultural products (seeds, fertilizers, pesticides) based on their location and preferences using AI-driven recommendations.

## 🚀 Features

- **Location-Based Search**: Supports GPS location and PIN code-based product discovery
- **Smart Ranking Algorithm**: Uses QQDP (Quality, Quantity, Distance, Price) scoring system
- **AI-Powered Recommendations**: Leverages Google's Gemini AI for personalized product explanations
- **Interactive Chat Interface**: User-friendly conversational UI for seamless interaction
- **Real-time Product Comparison**: Compares multiple options and highlights pros/cons
- **Nearby Seller Discovery**: Finds sellers within 25km radius

## 📋 Prerequisites

- Python 3.8+
- Google Gemini API key
- Flask web framework

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Hackathon-GDG-V2.git
   cd Hackathon-GDG-V2
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Copy `.env.example` to `.env`
   - Add your API keys:
     ```
     SECRET_KEY=your-secret-key-here
     GOOGLE_API_KEY=your-google-api-key
     GEMINI_MODEL_ID=gemini-pro
     PORT=5000
     ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the app**
   - Open your browser and navigate to `http://localhost:5000`

## 📁 Project Structure

```
Hackathon-GDG-V2/
├── app.py                  # Main Flask application
├── QQDP_scoring.py         # Product ranking algorithm
├── list_material.json      # Product database
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── static/
│   ├── css/
│   │   └── style.css      # Styling
│   ├── images/            # Image assets
│   └── js/
│       └── main.js        # Frontend JavaScript
└── templates/
    └── index.html         # Main HTML template
```

## 🧮 QQDP Scoring Algorithm

The system uses a sophisticated scoring algorithm that evaluates products based on:

- **Quality Score**: Combines product quality, reliability, and user reviews
- **Quantity Score**: Measures availability vs. required quantity
- **Distance Score**: Calculates proximity to farmer's location (Haversine formula)
- **Price Score**: Normalizes and compares prices across products

### Scoring Parameters

- Maximum distance: 25km
- Minimum quality threshold: 0.4
- Minimum quantity ratio: 0.8
- Preference levels: low (1), average (2), high (3)

## 🤖 AI Integration

The system integrates Google's Gemini AI to:
- Generate personalized product recommendations
- Explain why a product is the best choice
- Compare multiple options with pros and cons
- Provide farmer-friendly language and insights

## 🗺️ Location Features

### GPS Location
- Uses browser's Geolocation API for precise coordinates

### PIN Code Support
- Converts 6-digit Indian PIN codes to coordinates
- Uses PostalPinCode API for location resolution
- Fallback to major city coordinates

## 📊 Product Categories

- **Seeds**: Various crop seeds with quality ratings
- **Fertilizers**: Organic and chemical fertilizers
- **Pesticides**: Pest control solutions

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | `your-random-secret-key` |
| `GOOGLE_API_KEY` | Google Gemini API key | `AIza...` |
| `GEMINI_MODEL_ID` | Gemini model identifier | `gemini-pro` |
| `PORT` | Server port | `5000` |

## 🚦 Usage Flow

1. **Start Chat**: User initiates conversation
2. **Location**: System requests GPS or PIN code
3. **Category Selection**: User chooses product type (seeds/fertilizers/pesticides)
4. **Preference**: User specifies priority (quality/price/distance/quantity)
5. **Recommendations**: AI generates personalized recommendations
6. **Results**: Display top-ranked products with detailed comparison

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Your Name** - *Initial work* - [YourGitHub](https://github.com//Shreyas-patil07)

## 🙏 Acknowledgments

- Google Gemini AI for intelligent recommendations
- PostalPinCode API for location services
- GDG Hackathon for the opportunity

## 📧 Contact

For questions or support, please open an issue or contact [your-email@example.com](3shreyas2007@gmail.com)

---

Made with ❤️ for farmers


