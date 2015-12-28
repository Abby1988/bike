#coding:utf-8
from crank import Crank
from wheel import Wheel
from sprocket import Sprocket
from fatigue.fatigue import get_fatigue_func_by_level, get_fatigue_func

G = 9.8
SPAN = 0.1
        
class Bicycle(object):
    def __init__(self, front_weight, rear_weight, front_wheel, rear_wheel, crank, sprocket):
        self.front_weight = front_weight
        self.rear_weight = rear_weight
        self.front_wheel = front_wheel
        self.rear_wheel = rear_wheel
        self.crank = crank
        self.sprocket = sprocket
        
class Rider(object):
    def __init__(self, height, weight, level, bicycle, cadence=90):
        self.cadence = cadence
        self.height = height
        self.weight = weight
        self.bicycle = bicycle
        self._level = level
        self.fatigue_func = self.get_fatigue_func()
        
        
    @property
    def front_weight(self):
        return self.weight*0.4 + self.bicycle.front_weight - self.bicycle.front_wheel.weight
    @property
    def rear_weight(self):
        return self.weight*0.6 + self.bicycle.rear_weight - self.bicycle.rear_wheel.weight
    @property
    def all_weight(self):
        return self.weight + self.bicycle.front_weight + self.bicycle.rear_weight
    @property
    def K(self):
        # 空気抵抗係数 温度と表面積（身長体重から割り出せる？）に依存する
        return 0.15
    def W(self, v, x, wv=0):
        M = self.all_weight
        return v * ((0.1 * x + 0.05) * M + 0.15 * (v+wv)**2)
    
    def _get_level(self):
        return self._level
    def _set_level(self, value):
        self._level = value
        self.fatigue_func = self.get_fatigue_func()
    level = property(_get_level, _set_level)
    
    def get_fatigue_func(self):
        return get_fatigue_func_by_level(self.level)
    
    def acceleration(self, w, v, x=0):
        if v < 0:
            raise Exception("バックするな💢")
        
        M = self.all_weight
        R = self.bicycle.front_wheel.R
        
        resistor = 0
        
        # フラペの場合の限界トルク（推測）
        mf = M * G * self.bicycle.crank.length / R * 0.7
        if v == 0:
            f = mf
        else:
            f = min(w/v, mf)
            resistor += 0.005 * M * G   # 転がり抵抗
            
        resistor += 0.01 * x * M * G    # 傾斜抵抗
        resistor += self.K * v**2       # 空気抵抗
        
        I = self.bicycle.front_wheel.I + self.bicycle.rear_wheel.I #慣性モーメント
        
        return (f - resistor) * R**2 / (R**2 * M + I)
    
    def get_speed_by_grad(self, w, x):
        lb = 0
        ub = 100
        for i in range(100):
            mid = (lb + ub) / 2.
            if self.W(mid, x) < w:
                lb = mid
            else:
                ub = mid
        return mid
    
    def add_gear_change(self, gear_change, v, t):
        from math import pi
        R = self.bicycle.rear_wheel.R
        gear = v /(2*pi*R * self.cadence/60)
        
        crank = self.bicycle.crank.chainrings
        sprocket = self.bicycle.sprocket.chainrings
        
        def get_rear_gear(front_gear):
            lb = 0
            ub = len(sprocket)
            while lb + 1 < ub:
                mid = (lb + ub)/2
                if gear * sprocket[mid] > front_gear:
                    ub = mid
                else:
                    lb = mid
            if lb + 1 != len(sprocket) and abs(gear-float(sprocket[lb]) / front_gear) > abs(gear-float(sprocket[lb+1]) / front_gear):
                lb = lb + 1
            return lb
        
        front_gear = self._front_gear
        rear_gear = get_rear_gear(crank[front_gear])
        if front_gear == 0 and rear_gear < len(sprocket) * 1/4.:
            # アウターにチェンジ
            front_gear = 1
            rear_gear = get_rear_gear(crank[front_gear])
        elif front_gear == 1 and len(sprocket) * 3/4. < rear_gear:
            # インナーにチェンジ
            front_gear = 0
            rear_gear = get_rear_gear(crank[front_gear])
        
        if self.gear_changed_time < t and (self._front_gear != front_gear or self._rear_gear != rear_gear):
            if self._front_gear != front_gear:
                self._front_gear = front_gear
                self.gear_changed_time = t + 10
            if self._rear_gear != rear_gear:
                if self._rear_gear < rear_gear:
                    self._rear_gear += 1
                else:
                    self._rear_gear -= 1
                self.gear_changed_time = t + 1
                
            gear_change.append((t, (self._front_gear, self._rear_gear)))
        
        ratio = v / (2*pi*R * self.cadence/60 * crank[self._front_gear]/sprocket[self._rear_gear])
        if self._front_gear == 0 and self._rear_gear == len(sprocket)-1 and ratio > 1:
#             if self._lowgear > ratio:
#                 print t, self._lowgear
            self._lowgear = max(self._lowgear, ratio)
        if self._front_gear == 1 and self._rear_gear == 0 and ratio < 1:
            self._topgear = min(self._topgear, ratio)
            
    def get_time_by_splitted_course(self, splitted, watt=None):
        def get_message():
            crank = self.bicycle.crank.chainrings
            sprocket = self.bicycle.sprocket.chainrings       
            message = ""
            if self._lowgear != 1:
                ratio = self._lowgear
                message = "ローギア足りてねえ！" +\
                    "フロントを%dにするかリアを%dにしろ💢\n" % (int(crank[0] / ratio), int(sprocket[-1] * ratio + 1))
            if self._topgear != 1:
                ratio = self._topgear
                message = "トップギア足りてねえ!" +\
                    "フロントを%dにするかリアを%dにしろ💢\n" % (int(crank[1] / ratio + 1), int(sprocket[0] * ratio))
            return message[:-1]
            
        lb = 0
        ub = 10000
        for _ in range(30):
            mid = (lb + ub) / 2.
            if watt is None:
                w = self.fatigue_func(mid) * self.weight
            else:
                w = watt
            t = 0
            vel = 0
            self.gear_changed_time = 1
            gear_change = []
            self._lowgear = self._topgear = 1
            self._front_gear = len(self.bicycle.crank.chainrings) - 1
            self._rear_gear =  len(self.bicycle.sprocket.chainrings)/2
            gear_change.append((t, (self._front_gear, self._rear_gear), ""))
            for v in splitted:
                d = 0
                pacceleration = -1
                while d < v[0]:
                    # 実用上問題ない誤差を含む
                    acceleration = self.acceleration(w, vel, v[1] * 100. / v[0])
                    if acceleration == pacceleration:
                        t += (v[0] - d) / vel
                        d = v[0]
                    else:
                        vel += acceleration * SPAN
                        d += vel * SPAN
                        t += SPAN
                    pacceleration = acceleration
                    self.add_gear_change(gear_change, vel, t)
                                        
            if watt is not None:
                return t,  gear_change, get_message()
                    
            if mid < t:
                lb = mid
            else:
                ub = mid

        return mid, gear_change, get_message()
    
    def get_watt_by_splitted_course(self, alltime, splitted):
        lb = 0
        ub = 30 * self.weight
        for _ in range(30):
            mid = (lb + ub) / 2.
            t, gear_change, message = self.get_time_by_splitted_course(splitted, mid)
            if t > alltime:
                lb = mid
            else:
                ub = mid
        return mid, message
    
    def get_level(self, t, watt):
        return get_fatigue_func(t, float(watt)/self.weight)[:2]
        