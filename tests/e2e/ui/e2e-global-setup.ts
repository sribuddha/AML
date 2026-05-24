import { execSync } from "child_process";

async function globalSetup() {
  console.log("Seeding database for E2E tests...");
  execSync("python -m scripts.seed_db --force", {
    cwd: process.cwd().replace(/\\ui|\\tests.*/, ""),
    stdio: "inherit",
  });
  console.log("Database seeded.");
}

export default globalSetup;
