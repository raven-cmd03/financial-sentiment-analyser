import { Lock, KeyRound } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface LockedStateCardProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

/**
 * Friendly gated-state card for when the backend rejects a request because
 * `API_KEY` isn't configured. Used on Chat and Models where every endpoint
 * is API-key protected.
 */
export default function LockedStateCard({
  title = "Admin features are locked",
  description = "Set the API_KEY environment variable on the backend and VITE_API_KEY on the frontend, then reload. Without it we can't run fine-tuning jobs or the Groq-powered chat.",
  onRetry,
}: LockedStateCardProps) {
  return (
    <Card className="border-dashed bg-muted/30">
      <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Lock className="h-5 w-5" />
        </div>
        <div className="max-w-md space-y-1">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <a
              href="https://github.com/your-org/financial-sentiment-analyzer#configuration"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2"
            >
              <KeyRound className="h-4 w-4" />
              Configuration guide
            </a>
          </Button>
          {onRetry && (
            <Button size="sm" onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
