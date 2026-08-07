export type RepositoryRoute = {
  owner: string;
  name: string;
};

function decodeSegment(segment: string): string | null {
  try {
    const decoded = decodeURIComponent(segment);
    if (!decoded || decoded === "." || decoded === ".." || decoded.includes("/")) return null;
    return decoded;
  } catch {
    return null;
  }
}

export function repositoryFromRouteSegments(ownerSegment: string, repoSegment: string): RepositoryRoute | null {
  const owner = decodeSegment(ownerSegment);
  const name = decodeSegment(repoSegment.replace(/\.git$/, ""));
  if (!owner || !name) return null;
  return { owner, name };
}

export function repositoryPathname(repository: Pick<RepositoryRoute, "owner" | "name">): string {
  return `/repositories/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}`;
}
