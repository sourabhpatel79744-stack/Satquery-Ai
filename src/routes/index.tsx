import { createFileRoute } from "@tanstack/react-router";
import { CSSProperties, ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { ArrowRight, ImagePlus, Moon, RotateCcw, Search, Sparkles, Sun, X } from "lucide-react";
import { Button } from "../components/ui/button";
import earthImage from "../assets/satquery-earth.png";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SatQuery AI — Satellite Image Analysis" },
      { name: "description", content: "Compare satellite images and ask natural-language questions with SatQuery AI." },
    ],
  }),
  component: SatQuery,
});

type Upload = { file: File; url: string };
type Stage = "input" | "analyzing" | "results";
type EarthOrigin = { x: number; y: number; size: number };

function SatQuery() {
  const [before, setBefore] = useState<Upload | null>(null);
  const [after, setAfter] = useState<Upload | null>(null);
  const [question, setQuestion] = useState("");
  const [stage, setStage] = useState<Stage>("input");
  const [activeImage, setActiveImage] = useState<"before" | "after">("before");
  const [errors, setErrors] = useState({ before: "", after: "" });
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [earthOrigin, setEarthOrigin] = useState<EarthOrigin | null>(null);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [analysisMode, setAnalysisMode] = useState<"compare" | "single">("compare");
  const earthRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (stage !== "analyzing") return;
    const timer = window.setTimeout(() => setStage("results"), 3900);
    return () => window.clearTimeout(timer);
  }, [stage]);

  const setUpload = (kind: "before" | "after", file?: File) => {
    if (!file) return;
    if (!(["image/jpeg", "image/png"].includes(file.type))) {
      setErrors((current) => ({ ...current, [kind]: "Please choose a JPG or PNG image." }));
      return;
    }
    const upload = { file, url: URL.createObjectURL(file) };
    if (kind === "before") {
      if (before) URL.revokeObjectURL(before.url);
      setBefore(upload);
    } else {
      if (after) URL.revokeObjectURL(after.url);
      setAfter(upload);
    }
    setErrors((current) => ({ ...current, [kind]: "" }));
  };

  const removeUpload = (kind: "before" | "after") => {
    const current = kind === "before" ? before : after;
    if (current) URL.revokeObjectURL(current.url);
    kind === "before" ? setBefore(null) : setAfter(null);
    setErrors((value) => ({ ...value, [kind]: "" }));
  };

  const reset = () => {
    if (before) URL.revokeObjectURL(before.url);
    if (after) URL.revokeObjectURL(after.url);
    setBefore(null);
    setAfter(null);
    setQuestion("");
    setErrors({ before: "", after: "" });
    setActiveImage("before");
    setStage("input");
    setAnalysis(null);
    setConfidence(null);
  };

  const canAnalyze = Boolean(before && after && question.trim());
  const selected = activeImage === "before" ? before : after;
  
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(",")[1]);
      };
    });
  };

  const startAnalysis = async () => {
    if (!canAnalyze) return;
    const rect = earthRef.current?.getBoundingClientRect();
    if (rect) setEarthOrigin({ x: rect.left, y: rect.top, size: rect.width });
    setStage("analyzing");

    const beforeBase64 = await fileToBase64(before!.file);
    const afterBase64 = await fileToBase64(after!.file);

    try {
      const response = await fetch("https://shorts-dumpster-felt-tip.ngrok-free.dev/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          before_image: beforeBase64,
          after_image: afterBase64,
          question: question
        })
      });

      const result = await response.json();
      if (result.success) {
        setAnalysis(result.analysis);
        setConfidence(result.confidence);
      }
    } catch (error) {
      console.error("API Error:", error);
    }
  };
    const startAnalysisSingle = async () => {
    if (!before || !question.trim()) return;
    const rect = earthRef.current?.getBoundingClientRect();
    if (rect) setEarthOrigin({ x: rect.left, y: rect.top, size: rect.width });
    setStage("analyzing");

    const imageBase64 = await fileToBase64(before.file);

    try {
      const response = await fetch("https://shorts-dumpster-felt-tip.ngrok-free.dev/analyze-single", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: imageBase64,
          question: question
        })
      });

      const result = await response.json();
      if (result.success) {
        setAnalysis(result.analysis);
        setConfidence(0.85);
      }
    } catch (error) {
      console.error("API Error:", error);
    }
  };

  return (
    <main className={`${theme === "light" ? "light" : ""} space-shell min-h-dvh overflow-hidden bg-background text-foreground`}>
      <Starfield />
      {stage !== "analyzing" && <Navbar theme={theme} onToggleTheme={() => setTheme((value) => value === "dark" ? "light" : "dark")} />}

      {stage === "input" && (
        <section className="laptop-workspace relative z-10 mx-auto grid min-h-dvh max-w-[1360px] grid-cols-1 items-center gap-5 px-5 pb-8 pt-24 lg:grid-cols-[1.05fr_.95fr] lg:gap-10 lg:px-10 lg:pb-5 lg:pt-20">
          <div className="intro-copy flex min-h-[310px] flex-col items-center justify-center lg:min-h-0">
            <div className="earth-scene" aria-hidden="true">
              <div className="orbit orbit-one"><i /></div>
              <div className="orbit orbit-two"><i /></div>
              <div className="earth-glow" />
              <img ref={earthRef} src={earthImage} width={1024} height={1024} className="earth-image" alt="" />
            </div>
            <div className="mt-1 text-center lg:mt-5">
              <p className="eyebrow">VISION · LANGUAGE · EARTH</p>
              <h1 className="mt-2 text-3xl font-extrabold tracking-normal sm:text-4xl xl:text-5xl">See change. Ask anything.</h1>
              <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted-foreground sm:text-base">Upload two moments in time and explore what changed through natural language.</p>
            </div>
          </div>

         <section className="glass-panel input-panel mx-auto w-full max-w-2xl p-4 sm:p-6 lg:p-7" aria-label="Satellite image analysis">
  <div className="mb-5 flex items-center justify-between">
    <div>
      <p className="eyebrow">NEW ANALYSIS</p>
      <h2 className="mt-1 text-xl font-bold sm:text-2xl">Analyze imagery</h2>
    </div>
    <div className="flex gap-2">
      <button 
        onClick={() => setAnalysisMode("compare")}
        className={`px-3 py-1 text-xs rounded font-semibold ${analysisMode === "compare" ? "bg-primary-bright text-white" : "bg-surface-strong text-muted-foreground"}`}
      >
        Compare
      </button>
      <button 
        onClick={() => setAnalysisMode("single")}
        className={`px-3 py-1 text-xs rounded font-semibold ${analysisMode === "single" ? "bg-primary-bright text-white" : "bg-surface-strong text-muted-foreground"}`}
      >
        Single
      </button>
    </div>
  </div>

  {analysisMode === "compare" ? (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <UploadBox kind="before" label="Before Image" upload={before} error={errors.before} onUpload={setUpload} onRemove={removeUpload} />
        <UploadBox kind="after" label="After Image" upload={after} error={errors.after} onUpload={setUpload} onRemove={removeUpload} />
      </div>
      <label className="mt-5 block text-xs font-semibold uppercase text-muted-foreground">Your question</label>
      <div className="question-field mt-2 flex items-center gap-3">
        <Search className="h-5 w-5 shrink-0 text-primary-bright" />
        <input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") startAnalysis(); }} className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground" placeholder="Ask a question about these images..." />
      </div>
      <Button className="mt-4 w-full" disabled={!canAnalyze} onClick={startAnalysis}>
        <Sparkles className="h-4 w-4" /> Analyze imagery <ArrowRight className="h-4 w-4" />
      </Button>
    </>
  ) : (
    <>
      <div className="grid grid-cols-1 gap-3">
        <UploadBox kind="before" label="Satellite Image" upload={before} error={errors.before} onUpload={setUpload} onRemove={removeUpload} />
      </div>
      <label className="mt-5 block text-xs font-semibold uppercase text-muted-foreground">Your question</label>
      <div className="question-field mt-2 flex items-center gap-3">
        <Search className="h-5 w-5 shrink-0 text-primary-bright" />
        <input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") startAnalysisSingle(); }} className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground" placeholder="Ask a question about this image..." />
      </div>
      <Button className="mt-4 w-full" disabled={!before || !question.trim()} onClick={startAnalysisSingle}>
        <Sparkles className="h-4 w-4" /> Analyze image <ArrowRight className="h-4 w-4" />
      </Button>
    </>
  )}
  
  <p className="mt-3 text-center text-xs text-muted-foreground">JPG or PNG · Your images stay in this browser</p>
</section>
        </section>
      )}

      {stage === "analyzing" && before && <DiveSequence image={before.url} origin={earthOrigin} />}

      {stage === "results" && selected && (
        <section className="results-enter laptop-results relative z-10 mx-auto flex min-h-dvh max-w-[1360px] items-center px-5 pb-8 pt-24 lg:px-10">
          <div className="grid w-full grid-cols-1 gap-5 lg:grid-cols-[1.15fr_.85fr] lg:gap-7">
            <div className="glass-panel overflow-hidden p-2 sm:p-3">
              <div className="mb-2 flex items-center justify-between px-2 py-1">
                <div className="flex gap-1 rounded-md bg-surface-strong p-1" role="tablist">
                <Button variant={activeImage === "before" ? "default" : "ghost"} className="min-h-9 px-4 py-1" onClick={() => setActiveImage("before")}>Before</Button>
                  <Button variant={activeImage === "after" ? "default" : "ghost"} className="min-h-9 px-4 py-1" onClick={() => setActiveImage("after")}>After</Button>
                </div>
                <span className="hidden max-w-[45%] truncate text-xs text-muted-foreground sm:block">{selected.file.name}</span>
              </div>
              <div className="result-image-wrap"><img key={selected.url} src={selected.url} alt={`${activeImage} satellite view`} className="result-image" /></div>
            </div>
            <article className="glass-panel result-copy flex flex-col justify-center p-6 sm:p-8 lg:p-10">
              <div className="mb-6 flex items-center gap-3">
                <div className="result-icon"><Sparkles className="h-5 w-5" /></div>
                <div><p className="eyebrow">SATQUERY REPORT</p><h1 className="mt-1 text-2xl font-bold sm:text-3xl">Analysis Result</h1></div>
              </div>
              <div className="question-quote">"{question}"</div>
              <p className="mt-6 text-sm leading-7 text-secondary-foreground sm:text-base">{analysis || "Processing analysis..."}</p>
              <div className="mt-7 grid grid-cols-2 gap-3">
                <div className="metric"><span>Change signal</span><strong>{confidence ? `${Math.round(confidence * 100)}%` : "—"}</strong></div>
                <div className="metric"><span>Confidence</span><strong>{confidence ? `${Math.round(confidence * 100)}%` : "—"}</strong></div>
              </div>
              <Button variant="outline" className="mt-7 w-full" onClick={reset}><RotateCcw className="h-4 w-4" /> New Analysis</Button>
            </article>
          </div>
        </section>
      )}
    </main>
  );
}

function Navbar({ theme, onToggleTheme }: { theme: "dark" | "light"; onToggleTheme: () => void }) {
  return <header className="nav-glass fixed inset-x-0 top-0 z-40"><nav className="mx-auto flex h-16 max-w-[1360px] items-center justify-between px-5 lg:px-10"><a href="#top" className="flex items-center gap-2 font-extrabold"><span className="logo-mark"><span /></span>SatQuery <b className="text-primary-bright">AI</b></a><div className="flex items-center gap-1 sm:gap-3">{["Home", "How it Works", "About"].map((item) => <a key={item} href="#top" className="hidden rounded-md px-2 py-2 text-xs text-muted-foreground transition-colors hover:text-foreground sm:block sm:px-3 sm:text-sm">{item}</a>)}<Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} className="h-9 min-h-9 w-9">{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button></div></nav></header>;
}

function Starfield() {
  return <div className="starfield fixed inset-0 pointer-events-none" aria-hidden="true"><div className="stars stars-one" /><div className="stars stars-two" /><div className="ambient-beam" /></div>;
}

function UploadBox({ kind, label, upload, error, onUpload, onRemove }: { kind: "before" | "after"; label: string; upload: Upload | null; error: string; onUpload: (kind: "before" | "after", file?: File) => void; onRemove: (kind: "before" | "after") => void }) {
  const input = useRef<HTMLInputElement>(null);
  const choose = (event: ChangeEvent<HTMLInputElement>) => { onUpload(kind, event.target.files?.[0]); event.target.value = ""; };
  const drop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); onUpload(kind, event.dataTransfer.files?.[0]); };
  return <div><label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">{label}</label><div className={`upload-zone ${error ? "upload-error" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={drop}>{upload ? <><img src={upload.url} alt={`${label} preview`} className="absolute inset-0 h-full w-full object-cover" /><div className="thumbnail-shade" /><p className="absolute inset-x-3 bottom-3 truncate text-xs font-semibold">{upload.file.name}</p><Button variant="ghost" size="icon" aria-label={`Remove ${label}`} title={`Remove ${label}`} className="absolute right-2 top-2 h-8 min-h-8 w-8 bg-surface-strong" onClick={() => onRemove(kind)}><X className="h-4 w-4" /></Button></> : <Button variant="ghost" className="h-full w-full flex-col gap-2 rounded-none" onClick={() => input.current?.click()}><span className="upload-icon"><ImagePlus className="h-5 w-5" /></span><span className="text-sm font-semibold text-foreground">Drop or browse</span><span className="text-xs font-normal text-muted-foreground">JPG · PNG</span></Button>}<input ref={input} type="file" accept="image/jpeg,image/png" onChange={choose} className="sr-only" /></div>{error && <p className="mt-1.5 text-xs text-destructive">{error}</p>}</div>;
}

function DiveSequence({ image, origin }: { image: string; origin: EarthOrigin | null }) {
  const style = origin ? ({ "--earth-x": `${origin.x}px`, "--earth-y": `${origin.y}px`, "--earth-size": `${origin.size}px` } as CSSProperties) : undefined;
  return <div className="dive-sequence fixed inset-0 z-50 overflow-hidden bg-background" style={style} role="status" aria-live="polite"><div className="dive-stars" /><div className="launch-halo" /><img src={earthImage} width={1024} height={1024} className="dive-earth" alt="" /><div className="speed-lines" /><div className="atmosphere-flash" /><img src={image} className="dive-surface" alt="Uploaded satellite region" /><div className="surface-vignette" /><div className="scan-line" /><div className="dive-status"><span className="pulse-dot" /> Analyzing imagery...</div><div className="region-label"><span>Target acquired</span><strong>Analyzing region</strong></div></div>;
}
