import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  TrendingUp,
  MessageSquare,
  Newspaper,
  Brain,
  ArrowRight,
  AlertTriangle,
  Twitter,
} from 'lucide-react';

const steps = [
  {
    icon: BarChart3,
    title: 'Welcome to FinSentiment',
    description:
      'An intelligent platform that analyzes financial news sentiment and correlates it with market movements. This system uses FinBERT, a specialized AI model for financial text analysis.',
    note: 'Important: This system provides correlational insights, not investment advice. Sentiment is one of many factors influencing markets.',
  },
  {
    icon: Newspaper,
    title: 'News Collection & Analysis',
    description:
      'We automatically collect financial news from multiple sources including Google News, Yahoo Finance, Alpha Vantage, and RSS feeds. Each article is analyzed using FinBERT to determine positive, negative, or neutral sentiment with confidence scores.',
  },
  {
    icon: Twitter,
    title: 'Social Sentiment from X',
    description:
      'Track real-time social media buzz for any stock ticker. See bullish/bearish ratios, buzz scores, and trending tickers from X (Twitter) to understand what retail investors are discussing.',
  },
  {
    icon: TrendingUp,
    title: 'Market Correlations',
    description:
      'View statistical correlations between news sentiment and stock price movements using Pearson, Spearman, time-lagged, and rolling correlation methods. Understand how sentiment relates to price action over different time horizons.',
  },
  {
    icon: MessageSquare,
    title: 'AI-Powered Chat',
    description:
      'Ask questions about any stock, market trend, or sentiment pattern. Our Groq-powered RAG chatbot has full context of all collected news, sentiment data, and social media buzz to provide deep insights.',
  },
  {
    icon: Brain,
    title: 'Model Fine-Tuning',
    description:
      'Train and customize the FinBERT sentiment model on specialized financial datasets using your GPU. Compare model performance and switch between base and fine-tuned models for improved accuracy.',
  },
];

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();
  const step = steps[currentStep];
  const Icon = step.icon;

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {steps.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentStep(i)}
              className={`w-3 h-3 rounded-full transition-colors ${
                i === currentStep ? 'bg-blue-500' : i < currentStep ? 'bg-blue-800' : 'bg-gray-700'
              }`}
            />
          ))}
        </div>

        {/* Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-2xl">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-blue-500/10 rounded-2xl flex items-center justify-center">
              <Icon className="w-8 h-8 text-blue-400" />
            </div>
          </div>

          <h1 className="text-2xl font-bold text-white text-center mb-4">{step.title}</h1>
          <p className="text-gray-300 text-center leading-relaxed mb-6">{step.description}</p>

          {step.note && (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 flex gap-3 mb-6">
              <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              <p className="text-yellow-200 text-sm">{step.note}</p>
            </div>
          )}

          <div className="flex justify-between items-center mt-8">
            <button
              onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
              className={`text-gray-400 hover:text-white transition-colors ${
                currentStep === 0 ? 'invisible' : ''
              }`}
            >
              Back
            </button>

            {currentStep < steps.length - 1 ? (
              <button
                onClick={() => setCurrentStep(currentStep + 1)}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg transition-colors"
              >
                Next
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-500 text-white px-6 py-2.5 rounded-lg transition-colors"
              >
                Get Started
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Skip */}
        <div className="text-center mt-4">
          <button
            onClick={() => navigate('/')}
            className="text-gray-500 hover:text-gray-300 text-sm transition-colors"
          >
            Skip onboarding
          </button>
        </div>
      </div>
    </div>
  );
}
