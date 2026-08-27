export type PipelineStage =
  | 'pending' | 'import' | 'analyze' | 'curate' | 'refine' | 'render' | 'complete' | 'failed';

export interface MediaSummary {
  durationMs: number;
  width: number;
  height: number;
  fps: number;
  videoCodec: string;
  audioCodec?: string;
}

export interface ClipResult {
  id: string;
  title: string;
  startMs: number;
  endMs: number;
  qualityScore: number;
  outputUrl?: string;
}

export interface ProjectJob {
  id: string;
  title: string;
  stage: PipelineStage;
  progress: number;
  message: string;
  createdAt: string;
  sourceName?: string;
  media?: MediaSummary;
  clips: ClipResult[];
  error?: string;
}

export interface ProjectPreferences {
  language: 'auto' | 'pt' | 'en' | 'es';
  clipLength: 'short' | 'medium' | 'long';
  aspectRatio: '9:16' | '1:1' | '16:9';
  clipCount: number;
  prompt?: string;
  captions: boolean;
  autoReframe: boolean;
}
