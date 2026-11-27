export interface WireframeSection {
  title: string;
  components: string[];
}

export interface WireframeResponse {
  screen_name: string;
  sections: WireframeSection[];
}