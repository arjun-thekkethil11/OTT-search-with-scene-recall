export type Title = {
  id: string;
  title: string;
  year: number;
  runtime_min: number | null;
  type: "movie" | "series";
  seasons: number | null;
  genres: string[];
  languages: string[];
  countries: string[];
  imdb: number | null;
  overview: string;
  themes: string[];
  directors: string[];
  cast: string[];
  platforms: string[];
  poster_hue: number;
  poster_url: string | null;
  backdrop_url: string | null;
  tags: string[];
  remake_of: string | null;
  dual_role_cast: string[];
};

export type ParsedQuery = {
  raw: string;
  runtime_min: number | null;
  runtime_max: number | null;
  year_min: number | null;
  year_max: number | null;
  imdb_min: number | null;
  imdb_max: number | null;
  genres_include: string[];
  genres_exclude: string[];
  languages_include: string[];
  languages_exclude: string[];
  non_english: boolean;
  countries_include: string[];
  types: string[];
  platforms_include: string[];
  people_include: string[];
  dual_role: boolean;
  semantic_text: string;
};

export type MatchReason = {
  kind: "filter" | "semantic" | "miss";
  label: string;
  detail: string;
};

export type SearchHit = {
  title: Title;
  score: number;
  semantic: number;
  match_percent: number;
  reasons: MatchReason[];
};

export type SearchResponse = {
  query: string;
  parsed: ParsedQuery;
  results: SearchHit[];
  near_misses: SearchHit[];
  catalog_size: number;
};

export type RecallHit = {
  title: Title;
  confidence: number;
  why: string;
};

export type RecallResponse = {
  query: string;
  hits: RecallHit[];
  ai_used: boolean;
};

export type Facets = {
  genres: string[];
  languages: string[];
  countries: string[];
  platforms: string[];
  years: number[];
  types: string[];
};
