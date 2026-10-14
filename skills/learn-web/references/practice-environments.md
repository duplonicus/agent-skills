# Practice environments

Read this when the user has no account, instance or sandbox for the app they want to learn, or wants a safe place to practice write actions.

These are starting points to look up, not facts to repeat. Free tiers, trial lengths, card requirements and eligibility change often. Before recommending one:

- Open the vendor's own page with WebFetch.
- Quote the current terms to the user.
- Mention whether it needs a credit card.

## How to choose

Pick the first option that fits:

1. **Public demo or playground.** No sign-up, nothing to break. Best for read-heavy tools such as observability, dashboards and search.
2. **Self-hosted demo.** The user runs it locally, often with Docker, and gets realistic data with zero cost.
3. **Free tier or time-limited trial.** Best for admin consoles and cloud. Write actions are safe here, but billing and expiry matter.
4. **Their production environment.** Read-only stops only, unless they explicitly accept the risk of each write action.

## Starting points by category

- **Distributed tracing (Jaeger):** the Jaeger project ships HotROD, a sample app that generates traces for a local Jaeger. Check jaegertracing.io and the project's GitHub for the current Docker commands, because image names changed with Jaeger v2.
- **Dashboards and metrics (Grafana):** Grafana Labs runs a public demo instance. Search for "Grafana play" to find the current URL.
- **Log search (Kibana / Elastic):** Elastic offers a cloud trial, and Kibana ships sample data sets that can be loaded from its home page.
- **Datadog:** free trial. Check datadoghq.com for the current length and terms.
- **Microsoft 365 / Entra / Intune:** two options.
  - The M365 Developer Program sandbox. Eligibility has narrowed over the years, so check the program page before suggesting it.
  - A business trial tenant. Check microsoft.com for which plans currently offer one.
  - Trial tenants are separate from the user's personal Microsoft account.
- **AWS:** AWS Free Tier. The terms changed in 2025, so check aws.amazon.com/free.
  - Put a billing alarm or budget early in the tour.
  - Make cleanup of every resource a final stop.
- **Google Cloud:** a free trial with credits plus "always free" products. Check cloud.google.com/free.
  - A budget alert is worth a stop.
- **Azure:** Azure free account. Check azure.microsoft.com/free.
- **Ticketing and ITSM (Jira, ServiceNow, Zendesk):**
  - Jira Cloud has a free plan.
  - ServiceNow offers free Personal Developer Instances through its developer site.
  - Zendesk offers a trial.
  - Check each vendor's page.

## Teaching billing safety in cloud tours

When the tour involves a cloud provider, add these as real stops rather than footnotes:

1. **Early:** find the billing console and set a budget or alert.
2. **Each write stop:** say whether the resource bills while it exists.
3. **Final stop:** delete everything created during the tour, and confirm in the console that it's gone.
