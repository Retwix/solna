import express, { Request, Response } from "express";
import { insertFile } from "./db";

const app = express();

app.use(express.json());

app.get("/", (_req: Request, res: Response) => {
  res.send("Hello World!");
});

interface FileChangedRequestBody {
  file: string;
  event: string;
}

app.post("/file-changed", async (req: Request<unknown, unknown, FileChangedRequestBody>, res: Response) => {
  const { file, event } = req.body;

  try {
    await insertFile(file, event);
    res.status(200).send("File metadata stored");
  } catch (err) {
    console.error("DB insert error:", err);
    res.status(500).send("Internal Server Error");
  }
});

export default app;
