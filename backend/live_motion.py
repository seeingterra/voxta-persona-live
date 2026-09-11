"""Frame-rate-independent motion with quiet poses and irregular blinks."""
import math
import random


class NaturalMotion:
    def __init__(self,seed=None):
        self.random=random.Random(seed)
        self.last=None;self.next_pose=0.;self.pose=[0.,0.,0.];self.target=[0.,0.,0.]
        self.next_blink=0.;self.blink_start=-10.;self.mouth=0.;self.gaze=[0.,0.]
        self.smile=0.;self.brow=0.;self.posture=[0.,0.,0.]

    def update(self,t,mouth,state,gaze,emotion):
        dt=min(.25,max(0.,t-self.last)) if self.last is not None else 1/30
        self.last=t
        if t>=self.next_pose:
            self.next_pose=t+self.random.uniform(2.5,5.5)
            gain=.65 if state=='speaking' else .35
            self.target=[self.random.uniform(-1,1)*gain,self.random.uniform(-1,1)*gain*1.4,self.random.uniform(-1,1)*gain*.4]
        ease=1-math.exp(-dt/.85)
        for i in range(3):self.pose[i]+=(self.target[i]-self.pose[i])*ease
        for i in range(2):
            # Bound travel per second even when pointer input jumps across the stage.
            target=max(-.65,min(.65,float(gaze[i])))
            step=(target-self.gaze[i])*(1-math.exp(-dt/.5))
            self.gaze[i]+=max(-.65*dt,min(.65*dt,step))
        if not self.next_blink:self.next_blink=t+self.random.uniform(1.5,4)
        if t>=self.next_blink:
            self.blink_start=t;self.next_blink=t+self.random.uniform(2.8,6.8)
        elapsed=t-self.blink_start
        blink=math.sin(math.pi*elapsed/.46)**1.35 if 0<=elapsed<.46 else 0.
        desired=max(0.,min(.65,float(mouth))) if state=='speaking' else 0.
        tau=.045 if desired>self.mouth else .12
        self.mouth+=(desired-self.mouth)*(1-math.exp(-dt/tau))
        smile={'warm':.28,'excited':.4,'calm':.1,'sad':-.12,'angry':-.12}.get(emotion,0)
        brow={'surprised':1.6,'afraid':1.,'sad':.8,'angry':-1.5}.get(emotion,0)
        self.smile+=(smile-self.smile)*(1-math.exp(-dt/.4))
        self.brow+=(brow-self.brow)*(1-math.exp(-dt/.4))
        # Mood posture eases independently of the quiet idle pose; speech adds a small nod.
        desired_pose={'sad':(1.1,-.3,-.45),'angry':(-.55,0.,.15),
                      'warm':(-.2,.15,.4),'excited':(-.5,.2,.5),
                      'afraid':(.5,-.4,-.3),'surprised':(-.7,0.,0.)}.get(emotion,(0.,0.,0.))
        for i in range(3):self.posture[i]+=(desired_pose[i]-self.posture[i])*(1-math.exp(-dt/.9))
        pitch=self.pose[0]+self.posture[0]+math.sin(t*.82)*.12+math.sin(t*2.3)*self.mouth*.3
        yaw=self.pose[1]+self.posture[1]+self.gaze[0]*1.3
        return pitch,yaw,self.pose[2]+self.posture[2],blink,self.mouth,self.smile,self.brow,self.gaze

    def body(self,t,state):
        """Subtle normalized torso motion for transparent advanced-presence frames."""
        speaking=state=='speaking'
        breath=math.sin(t*(1.62 if speaking else 1.08))*.0032
        settle=math.sin(t*.43)*.0016+math.sin(t*.19)*.001
        rise=math.sin(t*(2.15 if speaking else 1.35))*(.0015 if speaking else .0008)
        return breath,settle,rise
