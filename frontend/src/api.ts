import type { Facets, RecallResponse, SearchResponse, Title } from "./types";

export async function searchCatalog(query: string): Promise<SearchResponse> {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: 24 }),
  });
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function recallScene(query: string): Promise<RecallResponse> {
  const res = await fetch("/api/recall", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: 6 }),
  });
  if (!res.ok) throw new Error("Recall failed");
  return res.json();
}

export async function loadFacets(): Promise<Facets> {
  const res = await fetch("/api/facets");
  if (!res.ok) throw new Error("Facets failed");
  return res.json();
}

export async function browseTitles(params: Record<string, string>): Promise<Title[]> {
  const qs = new URLSearchParams(params);
  const res = await fetch(`/api/titles?${qs}`);
  if (!res.ok) throw new Error("Browse failed");
  return res.json();
}
