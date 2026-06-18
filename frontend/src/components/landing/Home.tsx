import { motion, useScroll, useTransform } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { GitBranch, Layers, Code2, Bot, ArrowRight } from 'lucide-react';
import { useRef } from 'react';

export function Home() {
  const navigate = useNavigate();
  const targetRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: targetRef,
    offset: ["start start", "end start"]
  });

  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.5], [1, 0.8]);
  const y = useTransform(scrollYProgress, [0, 0.5], [0, 100]);

  // Snappy transition settings
  const snappyTransition: any = { type: 'spring', stiffness: 300, damping: 20 };

  return (
    <div className="bg-background min-h-screen text-foreground overflow-x-hidden selection:bg-primary/20">
      
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 p-6 flex justify-between items-center z-50 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-2 font-bold tracking-tight text-lg">
          <GitBranch className="w-6 h-6 text-primary" />
          <span>Band AI</span>
        </div>
        <div className="flex gap-4">
          <Link 
            to="/login"
            className="text-sm font-medium hover:text-primary transition-colors px-4 py-2"
          >
            Sign In
          </Link>
          <motion.div 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            transition={snappyTransition}
          >
            <Link 
              to="/login"
              className="inline-block text-sm font-semibold bg-primary text-primary-foreground px-5 py-2 rounded-full hover:bg-primary/90 transition-colors shadow-sm"
            >
              Get Started
            </Link>
          </motion.div>
        </div>
      </nav>

      {/* Hero Section */}
      <div ref={targetRef} className="relative min-h-screen flex flex-col items-center justify-center pt-20 px-4">
        
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none flex items-center justify-center">
          <motion.div 
            animate={{ 
              rotate: [0, 90, 0],
              borderRadius: ["20%", "50%", "20%"]
            }}
            transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
            className="absolute w-[800px] h-[800px] bg-primary/10 blur-[120px] rounded-full -top-40 -left-40"
          />
          <motion.div 
            animate={{ 
              rotate: [0, -90, 0],
              borderRadius: ["50%", "20%", "50%"]
            }}
            transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
            className="absolute w-[600px] h-[600px] bg-accent/20 blur-[100px] rounded-full bottom-0 right-0"
          />
        </div>

        <motion.div 
          style={{ opacity, scale, y }}
          className="relative z-10 flex flex-col items-center text-center max-w-4xl"
        >
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...snappyTransition, delay: 0.1 }}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-border shadow-sm text-sm font-medium mb-8 text-card-foreground"
          >
            <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse"></span>
            Band AI Control Plane 2.0 is live
          </motion.div>

          <motion.h1 
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...snappyTransition, delay: 0.2 }}
            className="text-6xl md:text-8xl font-extrabold tracking-tighter leading-[1.1] text-foreground"
          >
            Manage your <br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">
              Agent Swarm
            </span>
          </motion.h1>

          <motion.p 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...snappyTransition, delay: 0.3 }}
            className="mt-6 text-xl text-muted-foreground max-w-2xl font-light leading-relaxed"
          >
            Orchestrate multiple specialized AI models working together to build, review, and ship code faster than ever before.
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...snappyTransition, delay: 0.4 }}
            className="mt-10 flex gap-4"
          >
            <motion.div 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              transition={snappyTransition}
            >
              <Link 
                to="/login"
                className="group flex items-center gap-2 bg-primary text-primary-foreground px-8 py-4 rounded-full text-lg font-medium hover:bg-primary/90 transition-all shadow-lg"
              >
                Start Free Trial
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
            </motion.div>
          </motion.div>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1, duration: 1 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted-foreground"
        >
          <span className="text-xs uppercase tracking-widest font-semibold">Scroll</span>
          <motion.div 
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
            className="w-0.5 h-8 bg-gradient-to-b from-muted-foreground to-transparent"
          />
        </motion.div>
      </div>

      {/* Features Section */}
      <div className="bg-card py-32 px-4 border-t border-border">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-4xl font-bold tracking-tight mb-4">Unleash the Swarm</h2>
            <p className="text-neutral-500 text-lg">One instruction. Multiple agents. Infinite possibilities.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: <Bot className="w-8 h-8 text-indigo-500" />,
                title: "Multi-Model Architecture",
                desc: "Seamlessly route tasks between OpenAI, Anthropic, and Gemini models natively."
              },
              {
                icon: <Code2 className="w-8 h-8 text-blue-500" />,
                title: "Autonomous Code Execution",
                desc: "Agents don't just chat. They read, write, and execute code in your secure environment."
              },
              {
                icon: <Layers className="w-8 h-8 text-purple-500" />,
                title: "Hierarchical Delegation",
                desc: "CEO agents break down complex tasks and delegate them to specialized manager agents."
              }
            ].map((feature, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ ...snappyTransition, delay: i * 0.1 }}
                whileHover={{ y: -5 }}
                className="p-8 rounded-3xl bg-card border border-border hover:shadow-xl hover:shadow-primary/10 transition-all"
              >
                <div className="w-14 h-14 bg-secondary rounded-2xl flex items-center justify-center shadow-sm mb-6">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold mb-3 text-foreground">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
