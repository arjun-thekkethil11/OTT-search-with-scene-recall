import { useEffect, useMemo, useRef, useState } from "react";
import { browseTitles, loadFacets, recallScene, searchCatalog } from "./api";
import type { Facets, ParsedQuery, RecallResponse, SearchHit, SearchResponse, Title } from "./types";

export default function App() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [shelf, setShelf] = useState<Title[]>([]);
  const [filters, setFilters] = useState({ genre: "", language: "", country: "", year: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState<Title | null>(null);
  const [why, setWhy] = useState<SearchHit | null>(null);
  const [whyTargetId, setWhyTargetId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(true);
  const [recallOpen, setRecallOpen] = useState(false);
  const [recallQuery, setRecallQuery] = useState("");
  const [recallResult, setRecallResult] = useState<RecallResponse | null>(null);
  const [recallLoading, setRecallLoading] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);

  useEffect(() => {
    loadFacets().then(setFacets).catch(() => undefined);
    browseTitles({})
      .then((rows) => {
        setShelf(rows);
        setPicked(rows.slice().sort((a, b) => (b.imdb ?? 0) - (a.imdb ?? 0))[0] ?? null);
      })
      .catch(() => undefined);
  }, []);

  async function runSearch(next = query) {
    setLoading(true);
    setError(null);
    try {
      const result = await searchCatalog(next);
      setData(result);
      const first = result.results[0]?.title ?? null;
      setPicked(first);
      if (first && result.results[0]) {
        setWhy(result.results[0]);
        setWhyTargetId(first.id);
      } else {
        setWhy(null);
        setWhyTargetId(null);
      }
    } catch {
      setError("Could not reach the OpenShelf API. Start the backend on port 8001.");
    } finally {
      setLoading(false);
    }
  }

  async function runBrowse() {
    const params: Record<string, string> = {};
    if (filters.genre) params.genre = filters.genre;
    if (filters.language) params.language = filters.language;
    if (filters.country) params.country = filters.country;
    if (filters.year) params.year = filters.year;
    setLoading(true);
    setError(null);
    try {
      const rows = await browseTitles(params);
      setShelf(rows);
      setData(null);
      setPicked(rows[0] ?? null);
      setWhy(null);
      setWhyTargetId(null);
    } catch {
      setError("Catalog browse failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runRecall() {
    if (!recallQuery.trim()) return;
    setRecallLoading(true);
    setRecallError(null);
    try {
      const result = await recallScene(recallQuery);
      setRecallResult(result);
    } catch {
      setRecallError("Could not reach the recall service. Start the backend on port 8001.");
    } finally {
      setRecallLoading(false);
    }
  }

  function closeRecall() {
    setRecallOpen(false);
    setRecallError(null);
  }

  function pickFromRecall(t: Title) {
    setPicked(t);
    setWhy(lookupHit(t, data));
    setWhyTargetId(null);
    closeRecall();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const chips = useMemo(() => (data ? chipsFromParsed(data.parsed) : []), [data]);
  const featured = picked ?? shelf[0] ?? null;

  const rows = useMemo(() => buildRows(data, shelf, filters), [data, shelf, filters]);
  const heroWhy = data && why && whyTargetId && featured && whyTargetId === featured.id ? why : null;

  return (
    <div className="ott">
      <nav className="nav">
        <div className="nav-left">
          <span className="logo">OPENSHELF</span>
          <a href="#top-results">Home</a>
          <a href="#series">Series</a>
          <a href="#movies">Movies</a>
          <a href="#browse">Browse</a>
        </div>
        <div className="nav-right">
          {searchOpen && (
            <form
              className="nav-search"
              onSubmit={(e) => {
                e.preventDefault();
                void runSearch();
              }}
            >
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search titles, genres, languages…"
                aria-label="Search"
              />
            </form>
          )}
          <button type="button" className="icon-btn" onClick={() => setSearchOpen((v) => !v)} aria-label="Toggle search">
            ⌕
          </button>
          <button type="button" className="pill-btn" onClick={() => setRecallOpen(true)}>
            Forgot the name?
          </button>
        </div>
      </nav>

      {featured && <Billboard title={featured} loading={loading} why={heroWhy} />}

      <div className="rail-wrap">
        {error && <p className="error">{error}</p>}

        <div className="filter-strip" id="browse">
          {facets && (
            <div className="browse-bar">
              <select value={filters.genre} onChange={(e) => setFilters((f) => ({ ...f, genre: e.target.value }))}>
                <option value="">Genre</option>
                {facets.genres.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
              <select value={filters.language} onChange={(e) => setFilters((f) => ({ ...f, language: e.target.value }))}>
                <option value="">Language</option>
                {facets.languages.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
              <select value={filters.country} onChange={(e) => setFilters((f) => ({ ...f, country: e.target.value }))}>
                <option value="">Country</option>
                {facets.countries.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
              <select value={filters.year} onChange={(e) => setFilters((f) => ({ ...f, year: e.target.value }))}>
                <option value="">Year</option>
                {facets.years.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
              <button type="button" className="ghost" onClick={() => void runBrowse()}>
                Browse
              </button>
            </div>
          )}
        </div>

        {rows.map((row) => (
          <PosterRow
            key={row.id}
            id={row.id}
            label={row.label}
            chips={row.id === "top-results" ? chips : undefined}
            titles={row.titles}
            hits={row.hits}
            activeId={featured?.id}
            onPick={(t, hit) => {
              const next = hit ?? lookupHit(t, data);
              setPicked(t);
              if (next) {
                setWhy(next);
                setWhyTargetId(t.id);
              } else {
                setWhy(null);
                setWhyTargetId(null);
              }
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        ))}
      </div>

      {recallOpen && (
        <RecallModal
          query={recallQuery}
          onQueryChange={setRecallQuery}
          onSubmit={() => void runRecall()}
          loading={recallLoading}
          error={recallError}
          result={recallResult}
          onPick={pickFromRecall}
          onClose={closeRecall}
        />
      )}
    </div>
  );
}

function RecallModal({
  query,
  onQueryChange,
  onSubmit,
  loading,
  error,
  result,
  onPick,
  onClose,
}: {
  query: string;
  onQueryChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  error: string | null;
  result: RecallResponse | null;
  onPick: (t: Title) => void;
  onClose: () => void;
}) {
  return (
    <div className="recall-overlay" onClick={onClose}>
      <div className="recall-card" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="recall-close" onClick={onClose} aria-label="Close">
          ✕
        </button>
        <p className="eyebrow">Plot memory search</p>
        <h2>Describe the scene, not the title</h2>
        <p className="recall-sub">Half a scene. We’ll find the title.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
        >
          <textarea
            autoFocus
            rows={4}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder={
              'e.g. "a guy fakes being blind and gets pulled into a murder cover-up" or ' +
              '"kids play deadly playground games for prize money"'
            }
          />
          <button type="submit" className="play" disabled={loading || !query.trim()}>
            {loading ? "Thinking through the catalog…" : "Find it"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
        {result && (
          <div className="recall-results">
            {!result.ai_used && (
              <p className="recall-note">
                AI recall isn't configured on this server. Showing closest thematic matches
                instead of true plot recall.
              </p>
            )}
            {result.hits.length === 0 ? (
              <p className="recall-note">Nothing in this catalog matches that description confidently.</p>
            ) : (
              result.hits.map((h) => (
                <button type="button" key={h.title.id} className="recall-hit" onClick={() => onPick(h.title)}>
                  <Poster title={h.title} />
                  <div className="recall-hit-copy">
                    <b>{h.title.title}</b>
                    <em>
                      {h.title.year} · {h.title.type === "series" ? "Series" : "Film"}
                    </em>
                    <span className="recall-confidence">Best guess: {h.confidence}%</span>
                    <p>{h.why}</p>
                  </div>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Billboard({
  title,
  loading,
  why,
}: {
  title: Title;
  loading: boolean;
  why: SearchHit | null;
}) {
  const art = title.backdrop_url || title.poster_url;
  const whyReasons = (why?.reasons ?? []).filter((r) => r.kind === "filter" && r.label !== "Title");
  return (
    <header className="billboard">
      <div
        className="billboard-art"
        style={
          art
            ? { backgroundImage: `url(${art})` }
            : { background: `hsl(${title.poster_hue} 40% 12%)` }
        }
      />
      <div className="billboard-shade" />
      <div className="billboard-copy">
        <p className="eyebrow">{loading ? "Searching the catalog…" : title.type === "series" ? "Series" : "Film"}</p>
        <h1>{title.title}</h1>
        <p className="meta-line">
          {why ? <span className="match">{why.match_percent}% Match</span> : title.imdb != null ? <span>IMDb {title.imdb.toFixed(1)}</span> : null}
          <span>{title.year}</span>
          <span className="badge">TV-MA</span>
          {(title.tags ?? []).map((tag) => (
            <span key={tag} className={`badge version ${tag.toLowerCase()}`}>
              {tag}
            </span>
          ))}
          <span>{runtimeLabel(title)}</span>
          <span>{title.languages[0]}</span>
        </p>
        <p className="synopsis">{title.overview}</p>
        {title.remake_of ? <p className="version-note">Remake of {title.remake_of}</p> : null}
        <p className="genres">{title.genres.join(" · ")}</p>
        <div className="cta">
          <button type="button" className="play">
            ▶ Play
          </button>
          <button
            type="button"
            className="more"
            onClick={() => document.getElementById("top-results")?.scrollIntoView({ behavior: "smooth" })}
          >
            ℹ More like this
          </button>
        </div>
        {whyReasons.length > 0 && (
          <div className="hero-why" aria-live="polite">
            <strong>Why this matches</strong>
            <ul>
              {whyReasons.map((r, i) => (
                <li key={`${r.label}-${i}`} className={r.kind}>
                  {r.label}: {r.detail}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </header>
  );
}

function PosterRow({
  id,
  label,
  chips,
  titles,
  hits,
  activeId,
  onPick,
}: {
  id: string;
  label: string;
  chips?: string[];
  titles: Title[];
  hits?: SearchHit[];
  activeId?: string;
  onPick: (t: Title, hit: SearchHit | null) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  if (!titles.length) return null;
  const hitMap = new Map((hits ?? []).map((h) => [h.title.id, h]));

  function scrollBy(dir: number) {
    scroller.current?.scrollBy({ left: dir * 720, behavior: "smooth" });
  }

  return (
    <section className="row" id={id}>
      <div className="row-head">
        <h2>{label}</h2>
        {chips && chips.length > 0 && (
          <div className="chip-row">
            {chips.map((c) => (
              <span key={c} className="tag">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="row-stage">
        <button type="button" className="chev left" onClick={() => scrollBy(-1)} aria-label="Previous">
          ‹
        </button>
        <div className="scroller" ref={scroller}>
          {titles.map((t) => (
            <button
              key={t.id}
              type="button"
              className={t.id === activeId ? "tile active" : "tile"}
              onClick={() => onPick(t, hitMap.get(t.id) ?? null)}
            >
              <Poster title={t} />
              {(t.tags ?? []).length > 0 && (
                <span className="tile-tags">
                  {t.tags.filter((tag) => tag === "Remake" || tag === "Dubbed").join(" · ")}
                </span>
              )}
              <span className="tile-cap">
                <b>{t.title}</b>
                <em>
                  {t.year} · {t.genres[0] ?? t.type}
                </em>
              </span>
            </button>
          ))}
        </div>
        <button type="button" className="chev right" onClick={() => scrollBy(1)} aria-label="Next">
          ›
        </button>
      </div>
    </section>
  );
}

function Poster({ title }: { title: Title }) {
  const [failed, setFailed] = useState(false);
  if (title.poster_url && !failed) {
    return (
      <img
        className="poster-img"
        src={title.poster_url}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <div className="poster-fallback" style={{ background: `hsl(${title.poster_hue} 32% 18%)` }}>
      <strong>{title.title}</strong>
    </div>
  );
}

type Row = { id: string; label: string; titles: Title[]; hits?: SearchHit[] };

function buildRows(data: SearchResponse | null, shelf: Title[], filters: { genre: string; language: string }): Row[] {
  const rows: Row[] = [];
  if (data?.results.length) {
    rows.push({
      id: "top-results",
      label: "Top Results",
      titles: data.results.map((h) => h.title),
      hits: data.results,
    });
  }
  if (data?.near_misses.length) {
    rows.push({
      id: "close",
      label: "Because you watched nearby titles",
      titles: data.near_misses.map((h) => h.title),
      hits: data.near_misses,
    });
  }
  const trending = [...shelf].sort((a, b) => (b.imdb ?? 0) - (a.imdb ?? 0)).slice(0, 18);
  rows.push({ id: "trending", label: "Trending Now", titles: trending });
  rows.push({ id: "movies", label: "Movies", titles: shelf.filter((t) => t.type === "movie").slice(0, 18) });
  rows.push({ id: "series", label: "Series", titles: shelf.filter((t) => t.type === "series") });
  const korean = shelf.filter((t) => t.languages.includes("Korean") || t.countries.includes("South Korea"));
  rows.push({ id: "korean", label: "Korean TV Dramas & Films", titles: korean });
  const thrill = shelf.filter((t) => t.genres.includes("Thriller"));
  rows.push({ id: "thriller", label: "Suspenseful Thrillers", titles: thrill.slice(0, 18) });
  const netflix = shelf.filter((t) => t.platforms.includes("Netflix"));
  rows.push({ id: "netflix", label: "On Netflix", titles: netflix.slice(0, 18) });
  if (filters.genre || filters.language) {
    rows.unshift({
      id: "browse-slice",
      label: [filters.genre, filters.language].filter(Boolean).join(" · ") || "Catalog",
      titles: shelf,
    });
  }
  return rows.filter((r) => r.titles.length > 0);
}

function lookupHit(title: Title, data: SearchResponse | null): SearchHit | null {
  if (!data) return null;
  return [...data.results, ...data.near_misses].find((h) => h.title.id === title.id) ?? null;
}

function runtimeLabel(t: Title) {
  if (t.runtime_min) {
    const h = Math.floor(t.runtime_min / 60);
    const m = t.runtime_min % 60;
    return h ? `${h}h ${m}m` : `${m}m`;
  }
  if (t.seasons) return `${t.seasons} Season${t.seasons > 1 ? "s" : ""}`;
  return "Series";
}

function chipsFromParsed(p: ParsedQuery): string[] {
  const chips: string[] = [];
  if (p.runtime_min != null || p.runtime_max != null) {
    chips.push(`${p.runtime_min ?? 0}-${p.runtime_max ?? "∞"} min`);
  }
  chips.push(...p.genres_include);
  chips.push(...p.genres_exclude.map((g) => `no ${g}`));
  if (p.non_english) chips.push("non-English");
  chips.push(...p.languages_include);
  if (p.year_min != null || p.year_max != null) chips.push(`${p.year_min ?? "…"}-${p.year_max ?? "now"}`);
  if (p.imdb_min != null) chips.push(`IMDb > ${p.imdb_min < 7.01 ? "7" : p.imdb_min.toFixed(1)}`);
  chips.push(...p.countries_include);
  chips.push(...p.platforms_include);
  chips.push(...p.types);
  chips.push(...(p.people_include ?? []));
  if (p.dual_role) chips.push("dual role");
  return chips;
}
