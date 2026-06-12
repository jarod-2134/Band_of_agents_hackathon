import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { GitBranch, Loader2, Mail, Lock } from 'lucide-react';

export function Login() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Mock authentication delay
    setTimeout(() => {
      setIsLoading(false);
      navigate('/dashboard');
    }, 1500);
  };

  const snappyTransition = { type: 'spring', stiffness: 400, damping: 25 };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden text-foreground">
      
      {/* Animated Background Orbs */}
      <motion.div 
        animate={{ 
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3]
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute w-[500px] h-[500px] bg-primary/20 blur-[100px] rounded-full top-[-10%] right-[-5%]"
      />
      <motion.div 
        animate={{ 
          scale: [1, 1.5, 1],
          opacity: [0.2, 0.4, 0.2]
        }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        className="absolute w-[600px] h-[600px] bg-accent/20 blur-[120px] rounded-full bottom-[-10%] left-[-10%]"
      />

      <motion.div 
        initial={{ opacity: 0, y: 40, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={snappyTransition}
        className="relative z-10 w-full max-w-md bg-card/80 backdrop-blur-xl border border-border p-8 rounded-3xl shadow-2xl"
      >
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-primary/30">
            <GitBranch className="w-6 h-6 text-primary-foreground" />
          </div>
          <h2 className="text-2xl font-bold text-foreground">Welcome Back</h2>
          <p className="text-muted-foreground text-sm mt-1">Sign in to control your agent swarm</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground ml-1">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input 
                type="email" 
                required
                defaultValue="admin@band.ai"
                className="w-full bg-background border border-border text-foreground rounded-xl pl-10 pr-4 py-3 focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-all placeholder:text-muted-foreground"
                placeholder="you@company.com"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground ml-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input 
                type="password" 
                required
                defaultValue="password123"
                className="w-full bg-background border border-border text-foreground rounded-xl pl-10 pr-4 py-3 focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-all placeholder:text-muted-foreground"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="flex items-center justify-between text-sm mt-2 mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="rounded text-primary focus:ring-primary" />
              <span className="text-muted-foreground">Remember me</span>
            </label>
            <a href="#" className="text-primary font-medium hover:opacity-80">Forgot password?</a>
          </div>

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            disabled={isLoading}
            className="w-full bg-primary text-primary-foreground font-semibold rounded-xl py-3 flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors shadow-lg shadow-primary/25 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Authenticating...
              </>
            ) : (
              "Sign In"
            )}
          </motion.button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-8">
          Don't have an account? <a href="#" className="text-primary font-medium hover:opacity-80">Request Access</a>
        </p>
      </motion.div>
    </div>
  );
}
