import { Pool } from "pg";
import { randomUUID } from "crypto";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export const insertFile = async (file: string, event: string) => {
  const uuid = randomUUID();
  const now = new Date();

  const query = `
    INSERT INTO uploaded_files (id, filename, event, created_at)
    VALUES ($1, $2, $3, $4)
  `;

  await pool.query(query, [uuid, file, event, now]);
};
