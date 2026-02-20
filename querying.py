from tantivy import Index, Facet, Query, Occur, SchemaBuilder, FieldType

schema_builder = SchemaBuilder()
# Text-Felder
schema_builder.add_text_field("wikidata", stored=True)
schema_builder.add_text_field("url", stored=True)
schema_builder.add_text_field("title", stored=True, tokenizer_name='en_stem')
schema_builder.add_text_field("description", stored=True, tokenizer_name='en_stem')  # Multi-valued text field
schema_builder.add_text_field("image", stored=True)
schema_builder.add_text_field("locations", stored=True)
schema_builder.add_text_field("countries", stored=True)
schema_builder.add_text_field("genres", stored=True)
schema_builder.add_text_field("tmdb_overview", stored=True, tokenizer_name='en_stem')
schema_builder.add_text_field("tmdb_poster_path", stored=True)
schema_builder.add_text_field("trailer", stored=True)

# Integer-Felder
schema_builder.add_integer_field("id", stored=True, indexed=True)
schema_builder.add_integer_field("follower", stored=True, fast=True)
schema_builder.add_integer_field("score", stored=True, fast=True)
schema_builder.add_integer_field("start", stored=True, fast=True)
schema_builder.add_integer_field("tmdb_genre_ids", stored=True, indexed=True)
schema_builder.add_integer_field("tmdb_vote_count", stored=True, fast=True)

# Float-Felder
schema_builder.add_float_field("tmdb_popularity", stored=True, fast=True)
schema_builder.add_float_field("tmdb_vote_average", stored=True, fast=True)

# Facetten-Felder
schema_builder.add_facet_field("facet_locations")
schema_builder.add_facet_field("facet_countries")
schema_builder.add_facet_field("facet_genres")

schema = schema_builder.build()
index_path = "neu"
index = Index(schema, path=str(index_path))
searcher = index.searcher()

# Term Query / Facet field

def _demo_queries():
# text query
    text_q = Query.term_query(schema, "title", "crime")

# facet query
    facet_q = Query.term_query(schema, "facet_countries", Facet.from_string("/United States of America"))

# Kombination (MUST = logisches UND)
    q = Query.boolean_query([
    (Occur.Must, text_q),
    (Occur.Must, facet_q),
    ])

    q_hits = searcher.search(q, limit=10).hits
    for score, addr in q_hits:
    hit = searcher.doc(addr)
    print(hit['title'][0])
    print(f"https://www.youtube.com/watch?v={hit['trailer'][0]}")

    int_q = Query.term_query(schema, "id", 7)

    int_hits = searcher.search(int_q, limit=1).hits
    for score, addr in int_hits:
    hit = searcher.doc(addr)
    print(hit['title'][0])
    print(f"https://www.youtube.com/watch?v={hit['trailer'][0]}")

range_q = Query.range_query(schema,"follower", FieldType.Integer, lower_bound=5000, upper_bound=int(1e6))

range_hits = searcher.search(range_q, limit=10).hits
for score, addr in range_hits:
    hit = searcher.doc(addr)
    print(hit['title'][0])
    print(hit['follower'][0])

if __name__ == "__main__":
    _demo_queries()