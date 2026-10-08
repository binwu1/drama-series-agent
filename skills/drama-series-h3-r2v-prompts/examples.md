# Worked example: one shot → English Ref2VA

## Upstream (Chinese motion — no MiniMax tags)

```text
前段:黑海浪尖，筋斗云贴浪疾飞；布尔玛在云心死抱七珠盒。
中段:下一发擦云而过，她指节发白护紧盒子。布尔玛：「珠子绝不能掉！」悟空猛扳云沿侧翻躲开。
后段:云面重新压平，旗舰轮廓停在中远景。
运镜: 侧跟
结束帧:云面可读，旗舰在中远景。
```

## episode-run `video_prompt` (abbreviated English six-section)

```text
subject_definitions:
<Picture 1> is the first frame of [Shot 1], Bulma and Goku on the yellow nimbus over the sea.
<Subject 1> is Bulma, whose appearance must strictly match <Picture 2>.
<Subject 2> is Son Goku, whose appearance must strictly match <Picture 3>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] The target video begins from <Picture 1> with <Subject 1> and <Subject 2> dodging naval fire on the nimbus.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - opening composition continues.
<Subject 1> (appears in [Shot 1]): fully_preserved - identity locked to <Picture 2>.
<Subject 2> (appears in [Shot 1]): fully_preserved - identity locked to <Picture 3>.
<Audio 1>: reference - timbre guidance for <Subject 1> without copying the signal.
<Audio 2>: reference - timbre guidance for <Subject 2> without copying the signal.

detailed_description:
The target video is a dynamic live-action short-drama beat in vertical framing.
[Shot 1] The shot begins from <Picture 1>. Iron-gray warship cannons erupt; spray hits the cloud. <Subject 1> (S1) hugs the capsule box and, using the timbre referenced from <Audio 1>, says, <d>[Chinese] 珠子绝不能掉！</d> She closes her lips. <Subject 2> steers a hard side roll. Camera tracks sideways. Match duration to about 6 seconds. Lips stay closed except during spoken lines.

overall_soundscape:
Cannon thud, water columns, cloud spray.

non_diegetic_music:
N/A
```

Full smoke lines (older lean EN): `templates/h3_r2v_drama_project/run/EP001.episode-run.jsonl`.  
《起死》 rebuild default: `templates/起死/_build_run.py`.
