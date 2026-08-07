import { notFound } from "next/navigation";
import { Workspace } from "../../../_components/workspace";
import { repositoryFromRouteSegments } from "../../../_lib/repository";

export default async function RepositoryPage({
  params,
}: {
  params: Promise<{ owner: string; repo: string }>;
}) {
  const { owner, repo } = await params;
  const repository = repositoryFromRouteSegments(owner, repo);
  if (!repository) notFound();

  return <Workspace repository={repository} />;
}
