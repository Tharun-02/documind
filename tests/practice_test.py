from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt


paragraph = """
If I were to try that with my boss, I’d be thrown out on the spot. Still,
who knows whether that mightn’t be really good for me.
If I didn’t hold back for my parents’ sake, I would’ve quit
ages ago. I would’ve gone to the boss and told him just what
I think from the bottom of my heart. He would’ve fallen
right off his desk! How weird it is to sit up at the desk
and talk down to the employee from way up there. The boss
has trouble hearing, so the employee has to step up quite close to him.
Anyway, I haven’t completely given up that hope yet.
Once I’ve got together the money to pay off the parents’ debt to
him—that should take another five or six years—I’ll do it for sure.
Then I’ll make the big break. In any case, right now
I have to get up. My train leaves at five o’clock.

And he looked over at the alarm clock ticking away by
the chest of drawers. Good God, he thought. It was half past
six, and the hands were going quietly on. It was past
the half hour, already nearly quarter to. Could the alarm
have failed to ring? One saw from the bed that it was
properly set for four o’clock. Certainly it had rung.

Yes, but was it possible to sleep through this noise that
made the furniture shake? Now, it’s true he’d not slept
quietly, but evidently he’d slept all the more deeply.
Still, what should he do now? The next train left at seven
o’clock. To catch that one, he would have to go in a mad
rush. The sample collection wasn’t packed up yet, and he
really didn’t feel particularly fresh and active.

And even if he caught the train, there was no avoiding a
blow up with the boss, because the firm’s errand boy
would’ve waited for the five o’clock train and reported
the news of his absence long ago. He was the boss’s
minion, without backbone or intelligence.

Well then, what if he reported in sick? But that would be
extremely embarrassing and suspicious, because during his
five years’ service Gregor hadn’t been sick even once.
The boss would certainly come with the doctor from the
health insurance company and would reproach his parents
for their lazy son and cut short all objections with the
insurance doctor’s comments.

And besides, would the doctor in this case be totally wrong?
Apart from a really excessive drowsiness after the long sleep,
Gregor in fact felt quite well and even had a really strong appetite.
"""


# ============================================================
# 1. CHUNKING
# ============================================================

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=60,
    separators=["\n\n", "\n", " ", ""],
    length_function=len,
)

chunks = splitter.split_text(paragraph)

print("=" * 70)
print("CHUNKING")
print("=" * 70)

print(f"Original text length : {len(paragraph)} characters")
print(f"Number of chunks     : {len(chunks)}")
print()

for i, chunk in enumerate(chunks):
    print(f"--- Chunk {i} ({len(chunk)} characters) ---")
    print(chunk)
    print()


# ============================================================
# 2. CREATE EMBEDDINGS
# ============================================================

print("=" * 70)
print("EMBEDDINGS")
print("=" * 70)

# Small and beginner-friendly embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

embeddings = model.encode(chunks)

print(f"Number of embeddings : {len(embeddings)}")
print(f"Embedding dimensions : {len(embeddings[0])}")

print()
print("First chunk:")
print(chunks[0])

print()
print("First 10 numbers of its embedding:")
print(embeddings[0][:10])

print()
print("Complete embedding shape:")
print(embeddings.shape)


# ============================================================
# 3. COSINE SIMILARITY
# ============================================================

print()
print("=" * 70)
print("COSINE SIMILARITY")
print("=" * 70)

similarity = cosine_similarity(embeddings)

for i in range(min(5, len(chunks))):
    print(f"Chunk {i} similarities:")
    print(similarity[i])
    print()


# ============================================================
# 4. VISUALIZE EMBEDDINGS
# ============================================================

# Embeddings have 384 dimensions.
# We can't directly plot 384 dimensions.
# PCA reduces them to 2 dimensions for visualization.

from sklearn.decomposition import PCA

pca = PCA(n_components=2)

reduced_embeddings = pca.fit_transform(embeddings)

plt.figure(figsize=(10, 7))

plt.scatter(
    reduced_embeddings[:, 0],
    reduced_embeddings[:, 1]
)

for i, (x, y) in enumerate(reduced_embeddings):
    plt.annotate(
        f"Chunk {i}",
        (x, y)
    )

plt.title("Document Chunks in Embedding Space")
plt.xlabel("Embedding Dimension 1")
plt.ylabel("Embedding Dimension 2")

plt.show()