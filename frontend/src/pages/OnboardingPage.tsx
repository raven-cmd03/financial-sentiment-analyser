import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  TrendingUp,
  MessageSquare,
  Newspaper,
  Brain,
  ArrowRight,
  AlertTriangle,
  Twitter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

const steps = [
  {
    icon: BarChart3,
    title: "Welcome to FinSentiment",
    description:
      "An intelligent platform that analyzes financial news sentiment and correlates it with market movements. This system uses FinBERT, a specialized NLP model for financial text.",
    note: "This system provides correlational insights, not investment advice. Sentiment is one of many factors influencing markets.",
  },
  {
    icon: Newspaper,
    title: "News collection & analysis",
    description:
      "We automatically collect financial news from multiple sources including Google News, Yahoo Finance, Alpha Vantage, and RSS feeds. Each article is scored by FinBERT to determine positive, negative, or neutral sentiment with confidence.",
  },
  {
    icon: Twitter,
    title: "Social sentiment from X",
    description:
      "Track real-time social media buzz for any stock ticker. See bullish / bearish ratios, buzz scores, and trending tickers from X to understand what retail investors are discussing.",
  },
  {
    icon: TrendingUp,
    title: "Market correlations",
    description:
      "View statistical correlations between sentiment and price movements using Pearson, Spearman, time-lagged, and rolling methods to understand how sentiment relates to price action.",
  },
  {
    icon: MessageSquare,
    title: "AI-powered chat",
    description:
      "Ask questions about any ticker, sector, or trend. The Groq-powered RAG assistant has full context of all collected news, sentiment, and social buzz and always cites its sources.",
  },
  {
    icon: Brain,
    title: "Model fine-tuning",
    description:
      "Train the FinBERT sentiment model on specialized financial datasets using your GPU. Compare performance and switch between base and fine-tuned models at runtime.",
  },
];

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();
  const step = steps[currentStep];
  const Icon = step.icon;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-2xl">
        <div className="mb-8 flex justify-center gap-2">
          {steps.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentStep(i)}
              aria-label={`Step ${i + 1}`}
              aria-current={i === currentStep ? "step" : undefined}
              className={cn(
                "h-2 rounded-full transition-all",
                i === currentStep
                  ? "w-6 bg-primary"
                  : i < currentStep
                    ? "w-2 bg-primary/50"
                    : "w-2 bg-muted",
              )}
            />
          ))}
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="mb-6 flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                <Icon className="h-8 w-8 text-primary" aria-hidden="true" />
              </div>
            </div>

            <h1 className="mb-3 text-center text-2xl font-semibold tracking-tight text-foreground">
              {step.title}
            </h1>
            <p className="mb-6 text-center leading-relaxed text-muted-foreground">
              {step.description}
            </p>

            {step.note && (
              <Alert className="mb-6 border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{step.note}</AlertDescription>
              </Alert>
            )}

            <div className="mt-4 flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                className={cn(currentStep === 0 && "invisible")}
              >
                Back
              </Button>

              {currentStep < steps.length - 1 ? (
                <Button
                  onClick={() => setCurrentStep(currentStep + 1)}
                  className="gap-2"
                >
                  Next
                  <ArrowRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  onClick={() => navigate("/")}
                  className="gap-2 bg-positive text-white hover:bg-positive/90"
                >
                  Get started
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="mt-4 text-center">
          <button
            onClick={() => navigate("/")}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Skip onboarding
          </button>
        </div>
      </div>
    </div>
  );
}
