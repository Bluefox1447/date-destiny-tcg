# การ์ดตัวอย่างสำหรับทดสอบระบบ (ชื่อ/ค่าพลังเป็นของสมมติ ให้ Admin แก้หรือลบได้)
def E(code, name, color, cost, server, atk, crit, d, effect=''):
    return dict(code=code, name=name, type='entity', color=color, cost=cost, server=server,
                atk=atk, crit=crit, defense=d, effect=effect)

DEMO = [
    E('DD-0001', 'Neuro Spark', 'red', 1, 'Alpha', 1000, 100, 500, 'เมื่อลงสนาม: จั่วการ์ด 1 ใบ'),
    E('DD-0002', 'Byte Knight', 'blue', 2, 'Alpha', 1500, 100, 1000, 'ป้องกัน +500 ขณะอยู่ใน Protect Zone'),
    E('DD-0003', 'Pulse Runner', 'green', 2, 'Beta', 2000, 200, 500, ''),
    E('DD-0004', 'Echo Sage', 'purple', 3, 'Beta', 1000, 300, 1500, 'จ่าย 1 Code: ดูการ์ดบนสุดของเด็ค'),
    E('DD-0005', 'Null Hunter', 'black', 3, 'Gamma', 2500, 300, 1000, ''),
    E('DD-0006', 'Lumen Guard', 'white', 1, 'Gamma', 500, 0, 1500, ''),
    E('DD-0007', 'Flux Dancer', 'yellow', 2, 'Delta', 1800, 200, 800, ''),
    E('DD-0008', 'Core Titan', 'red', 4, 'Delta', 3500, 500, 2500, 'ไม่ถูกทำลายด้วยเอฟเฟคของฝ่ายตรงข้าม'),
    dict(code='DD-0101', name='Link Blade', type='ship', color='red', cost=1, link_atk=500, link_crit=100, link_def=0,
         effect='Link: เสริมพลังให้ Neurous ที่เชื่อม'),
    dict(code='DD-0102', name='Link Shield', type='ship', color='blue', cost=1, link_atk=0, link_crit=0, link_def=1000,
         effect='Link: เสริมพลังป้องกัน'),
    dict(code='DD-0201', name='Operator: Aurora', type='server', color='white', cost=0,
         effect='เมื่อเริ่มเทิร์น: ได้ Code เพิ่ม 1'),
    dict(code='DD-0202', name='Operator: Nyx', type='server', color='black', cost=0,
         effect='ครั้งละ 1 เทิร์น: ทิ้งการ์ด 1 ใบ จั่ว 1 ใบ'),
]
