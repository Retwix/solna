import { Router } from "express";
import { Pool } from "pg";
import pool from "../db";

const router = Router();

router.get("/photos", async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, filename, event as event_type, created_at as timestamp FROM uploaded_files ORDER BY created_at DESC"
    );
    res.status(200).json(result.rows);
  } catch (err) {
    console.error("Error fetching photos:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
