import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import re

# Download required NLTK data
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')

CATEGORY_KEYWORDS = {
    'groceries': ['supermarket', 'grocery', 'food', 'market'],
    'utilities': ['electricity', 'water', 'gas', 'internet', 'phone'],
    'transportation': ['uber', 'lyft', 'taxi', 'bus', 'train', 'fuel', 'parking'],
    'entertainment': ['restaurant', 'cinema', 'movie', 'theatre', 'concert'],
    'shopping': ['amazon', 'walmart', 'target', 'store', 'shop'],
    'healthcare': ['medical', 'doctor', 'pharmacy', 'hospital', 'health'],
}

def preprocess_text(text):
    """Clean and tokenize text"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    tokens = [t for t in tokens if t not in stop_words]
    return tokens

def categorize_transaction(description):
    """Categorize transaction using simple keyword matching"""
    tokens = preprocess_text(description)
    
    # Calculate matches for each category
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for token in tokens if token in keywords)
        category_scores[category] = matches
    
    # Find best matching category
    if max(category_scores.values()) > 0:
        best_category = max(category_scores.items(), key=lambda x: x[1])
        confidence = min(best_category[1] / len(tokens), 1.0)
        return best_category[0], confidence
    
    return 'other', 0.0
