import { defineRailway, github, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const repo = github("mykaelsss/formalytx", { branch: "main", checkSuites: false, rootDirectory: "/server" });

  const fastf1Cache = volume("formalytx-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "us-east4-eqdc4a", sizeMB: 5000 });
  const api = service("formalytx", {
    source: repo,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/server/Dockerfile", watchPatterns: ["/server/**"] },
    replicas: { "us-east4-eqdc4a": 1 },
    domains: ["api.formalytx.com"],
    volumeMounts: { "/home/nonroot/.fastf1": fastf1Cache },
  });
  const cron = service("formalytx-cron", {
    source: repo,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/server/Dockerfile" },
    start: "/usr/local/bin/docker-entrypoint.sh python -m app.archive --recent --allow-incomplete-when-final",
    replicas: { "us-east4-eqdc4a": 1 },
    deploy: { cronSchedule: "*/15 * * * *", restartPolicyType: "NEVER" },
  });

  return project("formalytx", {
    variables: { managed: false },
    resources: [api, cron, fastf1Cache],
  });
});
