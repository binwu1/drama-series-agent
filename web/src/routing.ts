/** Hash routes for Hermes shell — isolates pages by conversation id. */

export type Route =
  | { name: "chat" }
  | { name: "literary"; conversationId: string; episodeId?: string }
  | { name: "bible"; conversationId: string; fileName?: string }
  | { name: "cast"; conversationId: string }
  | { name: "jobs"; conversationId: string };

export function parseHash(hash: string = window.location.hash): Route {
  const raw = (hash || "#/").replace(/^#/, "") || "/";
  const parts = raw.split("/").filter(Boolean);
  // /c/:cid/literary[/:ep]
  if (parts[0] === "c" && parts[1] && parts[2] === "literary") {
    return {
      name: "literary",
      conversationId: decodeURIComponent(parts[1]),
      episodeId: parts[3] ? decodeURIComponent(parts[3]) : undefined,
    };
  }
  // /c/:cid/bible[/:file]
  if (parts[0] === "c" && parts[1] && parts[2] === "bible") {
    return {
      name: "bible",
      conversationId: decodeURIComponent(parts[1]),
      fileName: parts[3] ? decodeURIComponent(parts[3]) : undefined,
    };
  }
  // /c/:cid/cast
  if (parts[0] === "c" && parts[1] && parts[2] === "cast") {
    return {
      name: "cast",
      conversationId: decodeURIComponent(parts[1]),
    };
  }
  // /c/:cid/jobs
  if (parts[0] === "c" && parts[1] && parts[2] === "jobs") {
    return {
      name: "jobs",
      conversationId: decodeURIComponent(parts[1]),
    };
  }
  return { name: "chat" };
}

export function goChat() {
  window.location.hash = "#/";
}

export function goLiterary(cid: string, episodeId?: string) {
  const base = `#/c/${encodeURIComponent(cid)}/literary`;
  window.location.hash = episodeId
    ? `${base}/${encodeURIComponent(episodeId)}`
    : base;
}

export function goBible(cid: string, fileName?: string) {
  const base = `#/c/${encodeURIComponent(cid)}/bible`;
  window.location.hash = fileName
    ? `${base}/${encodeURIComponent(fileName)}`
    : base;
}

export function goCast(cid: string) {
  window.location.hash = `#/c/${encodeURIComponent(cid)}/cast`;
}

export function goJobs(cid: string) {
  window.location.hash = `#/c/${encodeURIComponent(cid)}/jobs`;
}

export function useHashRoute(): Route {
  // Imported lazily by App — use React hooks there
  return parseHash();
}
