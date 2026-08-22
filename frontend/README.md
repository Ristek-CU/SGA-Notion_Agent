# Frontend — SGA Notion Agent

Frontend dash tabel admin (React + Vite → nginx). Proxy `/api` ke backend service
`sga-notion-agent-selrus:3000`.

> Test path-filtered autodeploy: file ini hanya menyentuh `frontend/**`,
> sehingga seharusnya hanya service FRONTEND yang redeploy, backend tidak.