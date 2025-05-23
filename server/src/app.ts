import express, { Request, Response } from "express";

const app = express();

app.use(express.json());

app.get("/", (_req: Request, res: Response) => {
  res.send("Hello World!");
});

interface FileChangedRequestBody {
  file: string;
  event: string;
}

app.post("/file-changed", (req: Request<unknown, unknown, FileChangedRequestBody>, res: Response) => {
  const { file, event } = req.body;

  // TODO: Insert into DB, generate UUID, etc.
  console.log("File received:", file, "Event:", event);

  res.status(200).send("OK");
});

export default app;
