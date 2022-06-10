import snappi
import dpkt
api = snappi.api(location='https://clab-ixcb2b-ixia-c', verify=False)
cfg = api.config()
# this pushes object of type `snappi.Config` to controller
api.set_config(cfg)
# this retrieves back object of type `snappi.Config` from controller
cfg = api.get_config()

# config has an attribute called `ports` which holds an iterator of type
# `snappi.PortIter`, where each item is of type `snappi.Port` (p1 and p2)
p1, p2 = cfg.ports.port(name="p1", location="eth1").port(name="p2", location="eth2")

# config has an attribute called `layer1` which holds an iterator of type
# `snappi.Layer1Iter`, where each item is of type `snappi.Layer1` (ly)
ly = cfg.layer1.layer1(name="ly")[-1]
ly.speed = ly.SPEED_1_GBPS
# set same properties on both ports
ly.port_names = [p1.name, p2.name]

# config has an attribute called `captures` which holds an iterator of type
# `snappi.CaptureIter`, where each item is of type `snappi.Capture` (cp)
cp = cfg.captures.capture(name="cp")[-1]
cp.port_names = [p1.name, p2.name]

# config has an attribute called `flows` which holds an iterator of type
# `snappi.FlowIter`, where each item is of type `snappi.Flow` (f1, f2)
f1, f2 = cfg.flows.flow(name="flow p1->p2").flow(name="flow p2->p1")

# and assign source and destination ports for each
f1.tx_rx.port.tx_name, f1.tx_rx.port.rx_name = p1.name, p2.name
f2.tx_rx.port.tx_name, f2.tx_rx.port.rx_name = p2.name, p1.name

# configure packet size, rate and duration for both flows
f1.size.fixed, f2.size.fixed = 128, 256
for f in cfg.flows:
    # send 1000 packets and stop
    f.duration.fixed_packets.packets = 1000
    # send 1000 packets per second
    f.rate.pps = 1000
    
# configure packet with Ethernet, IPv4 and UDP headers for both flows
eth1, ip1, udp1 = f1.packet.ethernet().ipv4().udp()
eth2, ip2, udp2 = f2.packet.ethernet().ipv4().udp()

# set source and destination MAC addresses
eth1.src.value, eth1.dst.value = "00:AA:00:00:04:00", "00:AA:00:00:00:AA"
eth2.src.value, eth2.dst.value = "00:AA:00:00:00:AA", "00:AA:00:00:04:00"

# set source and destination IPv4 addresses
ip1.src.value, ip1.dst.value = "10.0.0.1", "10.0.0.2"
ip2.src.value, ip2.dst.value = "10.0.0.2", "10.0.0.1"

# set incrementing port numbers as source UDP ports
udp1.src_port.increment.start = 5000
udp1.src_port.increment.step = 2
udp1.src_port.increment.count = 10

udp2.src_port.increment.start = 6000
udp2.src_port.increment.step = 4
udp2.src_port.increment.count = 10

# assign list of port numbers as destination UDP ports
udp1.dst_port.values = [4000, 4044, 4060, 4074]
udp2.dst_port.values = [8000, 8044, 8060, 8074, 8082, 8084]

print(cfg)

# push configuration to controller
api.set_config(cfg)

# start packet capture on configured ports
cs = api.capture_state()
cs.state = cs.START
api.set_capture_state(cs)

# start transmitting configured flows
ts = api.transmit_state()
ts.state = ts.START
api.set_transmit_state(ts)

# create a port metrics request and filter based on port names
req = api.metrics_request()
req.port.port_names = [p.name for p in cfg.ports]
# include only sent and received packet counts
req.port.column_names = [req.port.FRAMES_TX, req.port.FRAMES_RX]

# fetch port metrics
res = api.get_metrics(req)

# calculate total frames sent and received across all configured ports
total_tx = sum([m.frames_tx for m in res.port_metrics])
total_rx = sum([m.frames_rx for m in res.port_metrics])
expected = sum([f.duration.fixed_packets.packets for f in cfg.flows])

for p in cfg.ports:
  # create capture request and filter based on port name
  req = api.capture_request()
  req.port_name = p.name
  # fetch captured pcap bytes and feed it to pcap parser dpkt
  pcap = dpkt.pcap.Reader(api.get_capture(req))
  for _, buf in pcap:
      # check if current packet is a valid UDP packet
      eth = dpkt.ethernet.Ethernet(buf)
      assert isinstance(eth.data.data, dpkt.udp.UDP)

pcap_bytes = api.get_capture(req)
with open('cap.pcap', 'wb') as p:
  p.write(pcap_bytes.read())

assert expected == total_tx and total_rx >= expected

