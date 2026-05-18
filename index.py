import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer

df = pd.read_csv("materi.csv", encoding="latin-1", skiprows=6)
df.columns = ["NO","TANGGAL","JAM","NAMA","SATKER","PERTANYAAN","JAWABAN"] + list(df.columns[7:])
df = df.dropna(subset=["PERTANYAAN", "JAWABAN"])
df = df[df["PERTANYAAN"].str.strip() != ""]
df = df[df["JAWABAN"].str.strip() != ""]

questions = df["PERTANYAAN"].tolist()
answers = df["JAWABAN"].tolist()

print(f"Total Q&A: {len(questions)}")
print(f"Sample: {questions[0][:50]}...")

vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=10000)
tfidf_matrix = vectorizer.fit_transform(questions)

data = {"vectorizer": vectorizer, "tfidf_matrix": tfidf_matrix, "questions": questions, "answers": answers}
with open("qna_index.pkl", "wb") as f:
    pickle.dump(data, f)

print(f"Indexed {len(questions)} Q&A pairs successfully!")
